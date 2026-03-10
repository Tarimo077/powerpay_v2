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
CO2_PER_KWH = 0.139972  # kg CO2 per kWh (adjust if needed) ~0.4999(grid emmission factor) x 0.28 (efficiency deficit of cookers)


def percent_change(current, previous):
    if previous == 0:
        return 0
    return round(((current - previous) / previous) * 100, 1)


def build_dashboard_context(is_superadmin=False, organization=None, period="7d", org_id=None):

    today = timezone.now().date()

    # -------- TIME FILTER --------
    if period == "30d":
        days_back = 30
    elif period == "90d":
        days_back = 90
    else:
        days_back = 7

    start_date = today - timedelta(days=days_back - 1)
    prev_start = start_date - timedelta(days=days_back)
    prev_end = start_date - timedelta(days=1)

    days = [start_date + timedelta(days=i) for i in range(days_back)]

    # -------- ORG FILTER --------
    if is_superadmin:
        organizations = Organization.objects.all()

        if org_id:
            devices = DeviceInfo.objects.filter(organization_id=org_id)
            transactions = Transaction.objects.filter(org_id=org_id)
        else:
            devices = DeviceInfo.objects.all()
            transactions = Transaction.objects.all()

    else:
        organizations = Organization.objects.filter(id=organization.id)
        devices = DeviceInfo.objects.filter(organization=organization)
        transactions = Transaction.objects.filter(org=organization)

    device_ids = devices.values_list("deviceid", flat=True)

    # -------- CURRENT PERIOD --------
    kwh_current = (
        DeviceData.objects
        .filter(deviceid__in=device_ids, time__date__gte=start_date)
        .aggregate(total=Sum("kwh"))["total"] or 0
    )

    money_current = (
        transactions.filter(time__date__gte=start_date)
        .aggregate(total=Sum("amount"))["total"] or 0
    )

    tx_current = transactions.filter(time__date__gte=start_date).count()

    # -------- PREVIOUS PERIOD --------
    kwh_previous = (
        DeviceData.objects
        .filter(deviceid__in=device_ids, time__date__range=(prev_start, prev_end))
        .aggregate(total=Sum("kwh"))["total"] or 0
    )

    money_previous = (
        transactions.filter(time__date__range=(prev_start, prev_end))
        .aggregate(total=Sum("amount"))["total"] or 0
    )

    tx_previous = transactions.filter(time__date__range=(prev_start, prev_end)).count()

    # -------- CO2 --------
    co2_current = kwh_current * CO2_PER_KWH
    co2_previous = kwh_previous * CO2_PER_KWH

    context = {
        "is_superadmin": is_superadmin,
        "organizations": organizations,

        "org_count": organizations.count(),
        "device_count": devices.count(),

        "kwh_total": round(kwh_current, 2),
        "kwh_change": percent_change(kwh_current, kwh_previous),

        "co2_total": round(co2_current, 2),
        "co2_change": percent_change(co2_current, co2_previous),


        "total_money": money_current,
        "money_change": percent_change(money_current, money_previous),

        "total_transactions": tx_current,
        "tx_change": percent_change(tx_current, tx_previous),

        "period": period,

        "line_chart_labels": [d.strftime("%b %d") for d in days],
    }

    # -------- DEVICE STATUS (NOT time filtered) --------
    status_counts = devices.values("active").annotate(count=Count("id"))

    context["device_status_counts"] = {
        "ON": next((x["count"] for x in status_counts if x["active"]), 0),
        "OFF": next((x["count"] for x in status_counts if not x["active"]), 0),
    }

    # -------- kWh LINE CHART (PER DEVICE) --------
    device_data = (
        DeviceData.objects
        .filter(deviceid__in=device_ids, time__date__gte=start_date)
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

    # -------- SUPERADMIN CHARTS --------
    if is_superadmin:

        money_by_org = (
            transactions
            .filter(time__date__gte=start_date)
            .values("org__name")
            .annotate(total=Sum("amount"))
            .order_by("org__name")
        )

        context["money_by_org_labels"] = [x["org__name"] for x in money_by_org]
        context["money_by_org_data"] = [float(x["total"]) for x in money_by_org]

        # -------- MONEY LINE CHART --------
        money_line_labels = [d.strftime("%b %d") for d in days]

        daily_money = (
            transactions
            .filter(time__date__gte=start_date)
            .annotate(day=TruncDate("time"))
            .values("org__name", "day")
            .annotate(total=Sum("amount"))
        )

        lookup = {}
        for row in daily_money:
            lookup.setdefault(row["org__name"], {})[row["day"]] = float(row["total"])

        money_line_data = {}
        for org in organizations:
            money_line_data[org.name] = [
                lookup.get(org.name, {}).get(day, 0)
                for day in days
            ]

        context["money_line_data"] = money_line_data
        context["money_line_labels"] = money_line_labels

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
    for period in ["7d", "30d", "90d"]:
        context = build_dashboard_context(
            is_superadmin=False,
            organization=organization
        )

        cache.set(
            f"dashboard_context_org_{org_id}_{period}",
            context,
            CACHE_TIMEOUT
        )


@shared_task
def cache_dashboard_superadmin():
    for period in ["7d", "30d", "90d"]:
        context = build_dashboard_context(is_superadmin=True, period=period)

        cache.set(
            f"dashboard_context_superadmin_{period}",
            context,
            CACHE_TIMEOUT
        )


@shared_task
def refresh_all_org_dashboards(): 
    for org in Organization.objects.all(): 
        cache_dashboard_for_org.delay(org.id)

@shared_task
def test_ceelry():
    print("hi")