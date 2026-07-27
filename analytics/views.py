from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncMonth, TruncWeek, TruncDate, ExtractHour
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import timedelta
import json

from customers.models import Customer
from sales.models import Sale
from transactions.models import Transaction
from devices.models import DeviceInfo, DeviceData


def get_period_range(period_str):
    now = timezone.now()
    mapping = {
        "7d": timedelta(days=7),
        "14d": timedelta(days=14),
        "30d": timedelta(days=30),
        "60d": timedelta(days=60),
        "90d": timedelta(days=90),
        "180d": timedelta(days=180),
        "365d": timedelta(days=365),
    }
    delta = mapping.get(period_str)
    if delta:
        return now - delta, now
    return None, now


def get_accessible_orgs(request):
    if hasattr(request, "accessible_orgs"):
        return request.accessible_orgs
    if request.user.role == "superadmin" or request.user.is_superuser:
        from organizations.models import Organization
        return Organization.objects.all()
    org = getattr(request.user, "organization", None)
    if org:
        from organizations.models import Organization
        return Organization.objects.filter(id=org.id)
    return []


@login_required
def dashboard(request):
    period = request.GET.get("period", "30d")
    start_date, end_date = get_period_range(period)
    org_id = request.GET.get("org")

    accessible_orgs = get_accessible_orgs(request)
    org_ids = [o.id for o in accessible_orgs] if accessible_orgs else []

    customer_qs = Customer.objects.filter(organization_id__in=org_ids)
    sale_qs = Sale.objects.filter(organization_id__in=org_ids)
    transaction_qs = Transaction.objects.filter(org_id__in=org_ids)
    device_qs = DeviceInfo.objects.filter(organization_id__in=org_ids)

    if org_id:
        customer_qs = customer_qs.filter(organization_id=org_id)
        sale_qs = sale_qs.filter(organization_id=org_id)
        transaction_qs = transaction_qs.filter(org_id=org_id)
        device_qs = device_qs.filter(organization_id=org_id)

    if start_date:
        customer_qs_period = customer_qs.filter(date__gte=start_date, date__lte=end_date)
        sale_qs_period = sale_qs.filter(date__gte=start_date, date__lte=end_date)
        transaction_qs_period = transaction_qs.filter(time__gte=start_date, time__lte=end_date)
    else:
        customer_qs_period = customer_qs
        sale_qs_period = sale_qs
        transaction_qs_period = transaction_qs

    # --- KPI STATS ---
    total_customers = customer_qs.count()
    new_customers = customer_qs_period.count()
    total_sales = sale_qs.count()
    new_sales = sale_qs_period.count()
    total_transactions = transaction_qs_period.count()
    total_revenue = transaction_qs_period.aggregate(total=Sum("amount"))["total"] or 0
    avg_transaction = transaction_qs_period.aggregate(avg=Avg("amount"))["avg"] or 0
    total_devices = device_qs.count()
    active_devices = device_qs.filter(active=True).count()

    # --- CUSTOMER ANALYTICS ---
    customers_by_gender = list(
        customer_qs.values("gender")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    gender_labels = json.dumps([dict(Customer.GENDER_CHOICES).get(g["gender"], g["gender"]) for g in customers_by_gender])
    gender_data = json.dumps([g["count"] for g in customers_by_gender])

    customers_by_county = list(
        customer_qs.exclude(county__isnull=True).exclude(county="")
        .values("county")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )
    county_labels = json.dumps([c["county"] for c in customers_by_county])
    county_data = json.dumps([c["count"] for c in customers_by_county])

    customer_growth = list(
        customer_qs_period.annotate(day=TruncDate("date"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    growth_labels = json.dumps([d["day"].strftime("%b %d") for d in customer_growth])
    growth_data = json.dumps([d["count"] for d in customer_growth])

    # --- SALES ANALYTICS ---
    sales_by_product = list(
        sale_qs.values("product_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    product_labels = json.dumps([dict(Sale.PRODUCT_TYPE_CHOICES).get(s["product_type"], s["product_type"]) for s in sales_by_product])
    product_data = json.dumps([s["count"] for s in sales_by_product])

    sales_by_mode = list(
        sale_qs.values("purchase_mode")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    mode_labels = json.dumps([dict(Sale.PURCHASE_MODE_CHOICES).get(m["purchase_mode"], m["purchase_mode"]) for m in sales_by_mode])
    mode_data = json.dumps([m["count"] for m in sales_by_mode])

    sales_trend = list(
        sale_qs_period.annotate(day=TruncDate("date"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    sales_trend_labels = json.dumps([d["day"].strftime("%b %d") for d in sales_trend])
    sales_trend_data = json.dumps([d["count"] for d in sales_trend])

    # --- TRANSACTION ANALYTICS ---
    revenue_trend = list(
        transaction_qs_period.annotate(day=TruncDate("time"))
        .values("day")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("day")
    )
    revenue_labels = json.dumps([d["day"].strftime("%b %d") for d in revenue_trend])
    revenue_data = json.dumps([float(d["total"]) for d in revenue_trend])
    tx_count_data = json.dumps([d["count"] for d in revenue_trend])

    transaction_by_hour = list(
        transaction_qs_period.annotate(hour=ExtractHour("time"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    hour_labels = json.dumps([f"{h['hour']:02d}:00" for h in transaction_by_hour])
    hour_data = json.dumps([h["count"] for h in transaction_by_hour])

    # --- DEVICE ANALYTICS ---
    device_active_count = active_devices
    device_inactive_count = total_devices - active_devices

    # --- CROSS-MODEL: Revenue per customer ---
    revenue_per_customer = float(total_revenue) / max(total_customers, 1)

    # --- CROSS-MODEL: Conversion rate (customers with sales) ---
    customers_with_sales = sale_qs.values("customer_id").distinct().count()
    conversion_rate = round((customers_with_sales / max(total_customers, 1)) * 100, 1)

    # --- LINKAGES TABLE ---
    search_q = request.GET.get("q", "").strip()
    page_number = request.GET.get("page", 1)
    page_size_options = [10, 25, 50, 100]
    try:
        page_size = int(request.GET.get("page_size", 10))
    except (TypeError, ValueError):
        page_size = 10
    if page_size not in page_size_options:
        page_size = 10

    linkage_sales = sale_qs.select_related("customer", "organization").order_by("-date")

    if search_q:
        linkage_sales = linkage_sales.filter(
            Q(customer__name__icontains=search_q) |
            Q(product_serial_number__icontains=search_q) |
            Q(customer__phone_number__icontains=search_q)
        )

    # Preload transactions for linkage (same pattern as paygo)
    all_org_ids = list(linkage_sales.values_list("organization_id", flat=True).distinct())
    all_txns = Transaction.objects.filter(org_id__in=all_org_ids).values("ref", "org_id", "amount", "time")
    txn_lookup = {}
    for t in all_txns:
        if not t["ref"]:
            continue
        last4 = t["ref"][-4:]
        key = (t["org_id"], last4)
        txn_lookup.setdefault(key, []).append(t)

    # Preload devices
    all_devices = DeviceInfo.objects.filter(organization_id__in=all_org_ids).values("deviceid", "active", "organization_id")
    device_lookup = {}
    for d in all_devices:
        last4 = d["deviceid"][-4:]
        key = (d["organization_id"], last4)
        device_lookup[key] = d["active"]

    # Build linkage rows
    linkage_rows = []
    for sale in linkage_sales:
        serial_last4 = sale.product_serial_number[-4:] if sale.product_serial_number else ""
        txn_key = (sale.organization_id, serial_last4)
        matched_txns = txn_lookup.get(txn_key, [])
        txns_sorted = sorted(matched_txns, key=lambda x: x["time"], reverse=True)
        total_paid = sum(float(t["amount"]) for t in matched_txns)
        last_payment = max((t["time"] for t in matched_txns), default=None)
        device_active = device_lookup.get(txn_key, None)

        linkage_rows.append({
            "customer_name": sale.customer.name if sale.customer else "N/A",
            "customer_id": sale.customer_id,
            "phone": sale.customer.phone_number if sale.customer else "",
            "serial": sale.product_serial_number,
            "product": dict(Sale.PRODUCT_TYPE_CHOICES).get(sale.product_type, sale.product_type),
            "purchase_mode": dict(Sale.PURCHASE_MODE_CHOICES).get(sale.purchase_mode, sale.purchase_mode),
            "sale_date": sale.registration_date,
            "organization": sale.organization.name if sale.organization else "",
            "txn_count": len(matched_txns),
            "total_paid": round(total_paid, 2),
            "last_payment": last_payment,
            "device_active": device_active,
            "sale_id": sale.id,
            "transactions": txns_sorted,
        })

    paginator = Paginator(linkage_rows, page_size)
    page_obj = paginator.get_page(page_number)

    context = {
        "period": period,
        "total_customers": total_customers,
        "new_customers": new_customers,
        "total_sales": total_sales,
        "new_sales": new_sales,
        "total_transactions": total_transactions,
        "total_revenue": total_revenue,
        "avg_transaction": round(float(avg_transaction), 2),
        "total_devices": total_devices,
        "active_devices": active_devices,
        "device_active_count": device_active_count,
        "device_inactive_count": device_inactive_count,
        "revenue_per_customer": round(revenue_per_customer, 2),
        "conversion_rate": conversion_rate,
        "gender_labels": gender_labels,
        "gender_data": gender_data,
        "county_labels": county_labels,
        "county_data": county_data,
        "growth_labels": growth_labels,
        "growth_data": growth_data,
        "product_labels": product_labels,
        "product_data": product_data,
        "mode_labels": mode_labels,
        "mode_data": mode_data,
        "sales_trend_labels": sales_trend_labels,
        "sales_trend_data": sales_trend_data,
        "revenue_labels": revenue_labels,
        "revenue_data": revenue_data,
        "tx_count_data": tx_count_data,
        "hour_labels": hour_labels,
        "hour_data": hour_data,
        # Linkages table
        "page_obj": page_obj,
        "page_size": page_size,
        "page_size_options": page_size_options,
        "search_query": search_q,
        "total_linkage_results": paginator.count,
    }
    return render(request, "analytics/dashboard.html", context)
