from celery import shared_task
from django.template.loader import render_to_string
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from organizations.models import Organization
from devices.models import DeviceInfo
from transactions.models import Transaction
from devices.models import DeviceData


CACHE_TIMEOUT = 60 * 5  # 5 minutes


def build_dashboard_context(is_superadmin=False, organization=None):
    today = timezone.now().date()
    first_day_month = today.replace(day=1)
    days = [today - timedelta(days=i) for i in reversed(range(7))]

    if is_superadmin:
        organizations = Organization.objects.all()
        devices = DeviceInfo.objects.all()
        transactions = Transaction.objects.all()
    else:
        organizations = Organization.objects.filter(id=organization.id)
        devices = DeviceInfo.objects.filter(organization=organization)
        transactions = Transaction.objects.filter(org=organization)

    device_ids = devices.values_list("deviceid", flat=True)

    # Summary
    kwh_today = (
        DeviceData.objects
        .filter(deviceid__in=device_ids, time__date=today)
        .aggregate(total=Sum("kwh"))["total"] or 0
    )

    kwh_month = (
        DeviceData.objects
        .filter(deviceid__in=device_ids, time__date__gte=first_day_month)
        .aggregate(total=Sum("kwh"))["total"] or 0
    )

    context = {
        "is_superadmin": is_superadmin,
        "org_count": organizations.count(),
        "device_count": devices.count(),
        "kwh_today": round(kwh_today, 2),
        "kwh_month": round(kwh_month, 2),
        "total_money": transactions.aggregate(total=Sum("amount"))["total"] or 0,
        "total_transactions": transactions.count(),
        "line_chart_labels": [d.strftime("%a %d") for d in days],
    }

    # Device Status
    status_counts = devices.values("active").annotate(count=Count("id"))
    context["device_status_counts"] = {
        "ON": next((x["count"] for x in status_counts if x["active"]), 0),
        "OFF": next((x["count"] for x in status_counts if not x["active"]), 0),
    }

    # kWh line chart (grouped)
    device_data = (
        DeviceData.objects
        .filter(deviceid__in=device_ids, time__date__gte=days[0])
        .annotate(day=TruncDate("time"))
        .values("deviceid", "day")
        .annotate(total_kwh=Sum("kwh"))
    )

    lookup = {}
    for row in device_data:
        lookup.setdefault(row["deviceid"], {})[row["day"]] = round(row["total_kwh"], 2)

    line_chart_data = {}
    for device in devices:
        line_chart_data[device.deviceid] = [
            lookup.get(device.deviceid, {}).get(day, 0)
            for day in days
        ]

    context["line_chart_data"] = line_chart_data

    # Superadmin extra charts
    if is_superadmin:
        money_by_org = (
            Transaction.objects
            .values("org__name")
            .annotate(total=Sum("amount"))
        )

        context["money_by_org_labels"] = [x["org__name"] for x in money_by_org]
        context["money_by_org_data"] = [float(x["total"]) for x in money_by_org]

        # Money over last 7 days per org
        money_line_data = {}
        for org in organizations:
            daily_totals = []
            for day in days:
                total = Transaction.objects.filter(
                    org=org,
                    time__date=day
                ).aggregate(total=Sum('amount'))['total'] or 0
                daily_totals.append(float(total))
            money_line_data[org.name] = daily_totals
        context['money_line_data'] = money_line_data
        context['money_line_labels'] = [d.strftime("%a %d") for d in days]

    return context


@shared_task
def cache_dashboard_for_org(org_id):
    organization = Organization.objects.get(id=org_id)

    context = build_dashboard_context(
        is_superadmin=False,
        organization=organization
    )

    cache.set(
        f"dashboard_html_org_{org_id}",
        context,
        CACHE_TIMEOUT
    )


@shared_task
def cache_dashboard_superadmin():
    context = build_dashboard_context(is_superadmin=True)

    cache.set(
        "dashboard_html_superadmin",
        context,
        CACHE_TIMEOUT
    )


@shared_task
def refresh_all_org_dashboards(): 
    for org in Organization.objects.all(): 
        cache_dashboard_for_org.delay(org.id)