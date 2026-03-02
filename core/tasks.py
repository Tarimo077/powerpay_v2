from celery import shared_task
from django.template.loader import render_to_string
from django.core.cache import cache
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import TruncDate, Upper, Trim
from django.utils import timezone
from datetime import timedelta
from organizations.models import Organization
from devices.models import DeviceInfo
from transactions.models import Transaction
from devices.models import DeviceData
from devices.services.energy import last_energy_timestamp
from django.core.paginator import Paginator


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

def build_transaction_context(user=None, is_superadmin=False, organization=None):
    """
    Returns a context dictionary for transactions summary & charts,
    similar to what transactions_page view renders.
    """
    today = timezone.now().date()
    date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
    start_date = date_list[0]

    # ---------------- BASE QUERYSET ----------------
    if is_superadmin:
        qs = Transaction.objects.select_related("org")
    else:
        qs = Transaction.objects.filter(org=organization)

    # ---------------- STATS ----------------
    stats = qs.aggregate(
        total_amount=Sum("amount"),
        last_7_days_amount=Sum("amount", filter=Q(time__date__gte=start_date)),
    )

    transaction_count = qs.count()

    # ---------------- PIE CHART ----------------
    money_by_org_labels = []
    money_by_org_data = []

    if is_superadmin:
        qs_org = (
            qs.annotate(org_name=Upper(Trim(F("org__name"))))
            .values("org_name")
            .annotate(total=Sum("amount"))
            .order_by("org_name")
        )
        money_by_org_labels = [x["org_name"] for x in qs_org]
        money_by_org_data = [float(x["total"]) for x in qs_org]

    # ---------------- LINE CHART ----------------
    money_line_labels = [d.strftime("%d %b") for d in date_list]
    money_line_data = {}

    # Initialize data for each organization
    if is_superadmin:
        all_orgs = qs.values_list("org__name", flat=True).distinct()
    else:
        all_orgs = [organization.name] if organization else []

    for name in all_orgs:
        money_line_data[name] = [0.0] * 7

    # Sum daily amounts for last 7 days
    daily_org_qs = (
        qs.filter(time__date__gte=start_date)
        .annotate(day=TruncDate("time"))
        .values("org__name", "day")
        .annotate(total=Sum("amount"))
    )

    date_to_idx = {date: i for i, date in enumerate(date_list)}
    for entry in daily_org_qs:
        name = entry["org__name"]
        day = entry["day"]
        total = float(entry["total"] or 0)
        if name in money_line_data and day in date_to_idx:
            idx = date_to_idx[day]
            money_line_data[name][idx] = total

    # ---------------- CONTEXT ----------------
    context = {
        "total_amount": stats["total_amount"] or 0,
        "last_7_days_amount": stats["last_7_days_amount"] or 0,
        "transaction_count": transaction_count,
        "money_by_org_labels": money_by_org_labels,
        "money_by_org_data": money_by_org_data,
        "money_line_labels": money_line_labels,
        "money_line_data": money_line_data,
    }

    return context

@shared_task
def cache_transaction_dashboard_for_org(org_id):
    organization = Organization.objects.get(id=org_id)
    context = build_transaction_context(
        user=None, 
        is_superadmin=False,
        organization=organization
    )

    cache.set(f"transaction_dashboard_org_{org_id}", context, CACHE_TIMEOUT)


@shared_task
def cache_transaction_dashboard_superadmin():
    context = build_transaction_context(is_superadmin=True)
    cache.set("transaction_dashboard_superadmin", context, CACHE_TIMEOUT)

@shared_task
def refresh_all_transaction_dashboards():
    for org in Organization.objects.all():
        cache_transaction_dashboard_for_org.delay(org.id)
    cache_transaction_dashboard_superadmin.delay()

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

