from celery import shared_task
from django.core.cache import cache
from django.db.models import Sum, Count, Q, F, Min
from django.db.models.functions import TruncDate, TruncMonth, Upper, Trim
from django.utils import timezone
from datetime import timedelta, date
from organizations.models import Organization
from devices.models import DeviceInfo
from transactions.models import Transaction
from devices.models import DeviceData



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
    elif period == "1d":
        days_back = 1
    elif period == "3d":
        days_back = 3
    elif period == "14d":
        days_back = 14
    elif period == "60d":
        days_back = 60
    elif period == "120d":
        days_back = 120
    elif period == "365d":
        days_back = 365
    elif period == "all":
        days_back = None
    else:
        days_back = 7

    # -------- HANDLE ALL TIME --------
    if days_back is None:
        forced_energy_start = date(2024, 9, 1)
        first_data = DeviceData.objects.aggregate(first=Min("time__date"))["first"]
        first_tx = Transaction.objects.aggregate(first=Min("time__date"))["first"]

        # 1. Define specific starts first
        energy_start_date = max(forced_energy_start, first_data) if first_data else forced_energy_start
        money_start_date = first_tx if first_tx else today

        # 2. Now define the general start_date (Fixes the UnboundLocalError)
        start_date = min(energy_start_date, money_start_date)

        # -------- Generate month buckets --------
        # Energy chart months
        delta_months_energy = (today.year - energy_start_date.year) * 12 + (today.month - energy_start_date.month)
        energy_days = []
        for i in range(delta_months_energy + 1):
            year = energy_start_date.year + (energy_start_date.month + i - 1) // 12
            month = (energy_start_date.month + i - 1) % 12 + 1
            energy_days.append(date(year, month, 1))

        # Money chart months
        delta_months_money = (today.year - money_start_date.year) * 12 + (today.month - money_start_date.month)
        money_days = []
        for i in range(delta_months_money + 1):
            year = money_start_date.year + (money_start_date.month + i - 1) // 12
            month = (money_start_date.month + i - 1) % 12 + 1
            money_days.append(date(year, month, 1))

        trunc_energy = TruncMonth("time")
        trunc_money = TruncMonth("time")

    else:
        # Standard period logic
        start_date = today - timedelta(days=days_back - 1)
        energy_start_date = start_date
        money_start_date = start_date

        energy_days = [start_date + timedelta(days=i) for i in range(days_back)]
        money_days = [start_date + timedelta(days=i) for i in range(days_back)]

        trunc_energy = TruncDate("time")
        trunc_money = TruncDate("time")

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
    kwh_current = DeviceData.objects.filter(deviceid__in=device_ids, time__date__gte=energy_start_date).aggregate(total=Sum("kwh"))["total"] or 0
    money_current = transactions.filter(time__date__gte=money_start_date).aggregate(total=Sum("amount"))["total"] or 0
    tx_current = transactions.filter(time__date__gte=start_date).count()

    # -------- PREVIOUS PERIOD --------
    prev_start = min(energy_start_date, money_start_date) - timedelta(days=1)
    prev_end = prev_start
    kwh_previous = DeviceData.objects.filter(deviceid__in=device_ids, time__date__range=(prev_start, prev_end)).aggregate(total=Sum("kwh"))["total"] or 0
    money_previous = transactions.filter(time__date__range=(prev_start, prev_end)).aggregate(total=Sum("amount"))["total"] or 0
    tx_previous = transactions.filter(time__date__range=(prev_start, prev_end)).count()

    # -------- CO2 --------
    co2_current = kwh_current * CO2_PER_KWH
    co2_previous = kwh_previous * CO2_PER_KWH

    # -------- CONTEXT --------
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
    }

    # -------- DEVICE STATUS --------
    status_counts = devices.values("active").annotate(count=Count("id"))
    context["device_status_counts"] = {
        "ON": next((x["count"] for x in status_counts if x["active"]), 0),
        "OFF": next((x["count"] for x in status_counts if not x["active"]), 0),
    }

    # -------- ENERGY LINE CHART --------
    energy_data = DeviceData.objects.filter(deviceid__in=device_ids, time__date__gte=energy_start_date).annotate(day=trunc_energy).values("day").annotate(total_kwh=Sum("kwh"))
    energy_lookup = {row["day"].date() if hasattr(row["day"], "date") else row["day"]: round(row["total_kwh"], 2) for row in energy_data}
    context["energy_line_data"] = [energy_lookup.get(d, 0) for d in energy_days]
    
    # Label formatting based on period
    if period == "all":
        context["energy_line_labels"] = [d.strftime("%b %Y") for d in energy_days]
    else:
        context["energy_line_labels"] = [d.strftime("%b %d") for d in energy_days]

    # -------- SUPERADMIN MONEY CHART --------
    if is_superadmin:
        money_by_org = transactions.filter(time__date__gte=money_start_date).values("org__name").annotate(total=Sum("amount")).order_by("org__name")
        context["money_by_org_labels"] = [x["org__name"] for x in money_by_org]
        context["money_by_org_data"] = [float(x["total"]) for x in money_by_org]

        # Money line chart
        daily_money = transactions.filter(time__date__gte=money_start_date).annotate(day=trunc_money).values("org__name", "day").annotate(total=Sum("amount"))
        money_lookup = {}
        for row in daily_money:
            day_key = row["day"].date() if hasattr(row["day"], "date") else row["day"]
            money_lookup.setdefault(row["org__name"], {})[day_key] = float(row["total"])

        money_line_data = {}
        for org in organizations:
            values = [money_lookup.get(org.name, {}).get(d, 0) for d in money_days]
            if any(v > 0 for v in values):
                money_line_data[org.name] = values

        context["money_line_data"] = money_line_data
        
        if period == "all":
            context["money_line_labels"] = [d.strftime("%b %Y") for d in money_days]
        else:
            context["money_line_labels"] = [d.strftime("%b %d") for d in money_days]

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
    for period in ["1d", "3d", "7d", "14d", "30d", "60d", "90d", "120d", "365d", "all"]:
        context = build_dashboard_context(
            is_superadmin=False,
            organization=organization,
            period=period,
            org_id=org_id, 
        )

        cache.set(
            f"dashboard_context_org_{org_id}_{period}",
            context,
            CACHE_TIMEOUT
        )


@shared_task
def cache_dashboard_superadmin():

    org_ids = list(Organization.objects.values_list("id", flat=True))

    for period in ["1d", "3d", "7d", "14d", "30d", "60d", "90d", "120d", "365d", "all"]:

        # Cache "All organizations"
        context = build_dashboard_context(
            is_superadmin=True,
            period=period
        )

        cache.set(
            f"dashboard_context_superadmin_all_{period}",
            context,
            CACHE_TIMEOUT
        )

        # Cache each organization
        for org_id in org_ids:

            context = build_dashboard_context(
                is_superadmin=True,
                period=period,
                org_id=org_id
            )

            cache.set(
                f"dashboard_context_superadmin_org_{org_id}_{period}",
                context,
                CACHE_TIMEOUT
            )

@shared_task
def refresh_all_org_dashboards(): 
    for org in Organization.objects.all(): 
        cache_dashboard_for_org.delay(org.id)
