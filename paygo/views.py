
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum, Max
from django.utils import timezone
from sales.models import Sale
from transactions.models import Transaction
from devices.models import DeviceInfo
from .models import PayGoSettings
from .forms import PayGoSettingsForm
from .utils import get_payment_plan_details
from core.org_checker import get_accessible_organizations
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone


STATUS_LABELS = {
    "fully_paid": "Fully Paid",
    "on_track": "On Track",
    "at_risk": "At Risk",
    "overdue": "Overdue",
}

def get_status(total_paid, expected_paid, total_price):
    if total_paid >= total_price:
        return "fully_paid", "blue"

    if expected_paid <= 0:
        return "on_track", "green"

    gap = total_paid - expected_paid

    if gap >= 0:
        return "on_track", "green"
    elif gap >= -0.3 * expected_paid:
        return "at_risk", "orange"
    return "overdue", "red"


def paygo_sales_view(request):

    user = request.user
    is_superadmin = user.is_superuser or getattr(user, "role", "") == "superadmin"

    # -------- QUERY PARAMS --------
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "")
    sort = request.GET.get("sort", "balance")
    direction = request.GET.get("dir", "desc")
    page = request.GET.get("page", 1)

    # -------- SALES BASE --------
    if is_superadmin:
        sales = Sale.objects.filter(
            purchase_mode="P",
            payment_plan__in=["Plan_1", "Plan_2"]
        ).select_related("customer", "organization")
    else:
        orgs = get_accessible_organizations(user)
        sales = Sale.objects.filter(
            purchase_mode="P",
            payment_plan__in=["Plan_1", "Plan_2"],
            organization__in=orgs
        ).select_related("customer", "organization")

    today = timezone.now().date()

    # -------- PRELOAD TRANSACTIONS --------
    org_ids = sales.values_list("organization_id", flat=True)
    transactions = Transaction.objects.filter(
        org_id__in=org_ids
    ).values("ref", "org_id", "amount", "time")

    txn_lookup = {}
    for t in transactions:
        if not t["ref"]:
            continue
        last4 = t["ref"][-4:]
        key = (t["org_id"], last4)
        txn_lookup.setdefault(key, []).append(t)

    # -------- PRELOAD DEVICES --------
    devices = DeviceInfo.objects.filter(
        organization_id__in=org_ids
    ).values("deviceid", "active")

    device_lookup = {d["deviceid"][-4:]: d["active"] for d in devices}

    # -------- PRELOAD SETTINGS --------
    settings_map = {s.sale_id: s for s in PayGoSettings.objects.filter(sale__in=sales)}

    rows = []

    # -------- BUILD ROWS --------
    for sale in sales:

        plan = get_payment_plan_details(sale.payment_plan)
        if not plan:
            continue

        serial_last4 = sale.product_serial_number[-4:]
        key = (sale.organization_id, serial_last4)
        txns = txn_lookup.get(key, [])

        total_paid = sum(float(t["amount"]) for t in txns)
        last_payment = max((t["time"] for t in txns), default=None)

        # -------- PAYMENT LOGIC --------
        # Use sale.date as start
        start_date = sale.date.date() if sale.date else today
        weeks_elapsed = max((today - start_date).days // 7, 0)
        expected_paid = plan["deposit"] + (weeks_elapsed * plan["weekly_payment"])
        expected_paid = min(expected_paid, plan["total_price"])
        balance = max(plan["total_price"] - total_paid, 0)

        status_key, color = get_status(total_paid, expected_paid, plan["total_price"])

        # -------- SCHEDULE CALCULATION --------
        if total_paid >= plan["total_price"]:
            days_behind = 0
            days_to_next = 0
        else:
            expected_weeks = (total_paid - plan["deposit"]) // plan["weekly_payment"] if plan["weekly_payment"] > 0 else 0
            expected_next_payment_date = start_date + timezone.timedelta(weeks=expected_weeks + 1)
            days_to_next = max((expected_next_payment_date - today).days, 0)
            days_behind = max((today - expected_next_payment_date).days, 0)

        schedule_text = ""
        if days_behind > 0:
            schedule_text = f"{days_behind}d behind payment"
        elif days_to_next > 0:
            schedule_text = f"{days_to_next}d to payment"
        else:
            schedule_text = "On Time"

        # -------- DEVICE --------
        device_active = device_lookup.get(serial_last4, False)
        paygo_settings = settings_map.get(sale.id)

        row = {
            "sale": sale,
            "serial": sale.product_serial_number,
            "customer": sale.customer.name if sale.customer else "",
            "total_paid": round(total_paid, 2),
            "balance": round(balance, 2),
            "status": status_key,
            "status_label": STATUS_LABELS.get(status_key, status_key),
            "color": color,
            "last_payment": last_payment,
            "device_active": device_active,
            "auto_disable": paygo_settings.auto_disable if paygo_settings else False,
            "schedule": schedule_text,
        }

        rows.append(row)

    # -------- SEARCH FILTER --------
    if search_query:
        rows = [r for r in rows if search_query.lower() in r["serial"].lower()
                or search_query.lower() in r["customer"].lower()]

    # -------- STATUS FILTER --------
    if status_filter:
        rows = [r for r in rows if r["status"] == status_filter]

    # -------- STATS --------
    stats = {k: 0 for k in STATUS_LABELS.keys()}
    for r in rows:
        stats[r["status"]] += 1

    # -------- SORTING --------
    allowed_sorts = {"balance": "balance", "paid": "total_paid", "serial": "serial", "customer": "customer"}
    sort_key = allowed_sorts.get(sort, "balance")
    reverse = direction == "desc"
    rows.sort(key=lambda x: x[sort_key], reverse=reverse)

    # -------- PAGINATION --------
    paginator = Paginator(rows, 10)
    page_obj = paginator.get_page(page)

    # -------- NEXT DIR --------
    next_dirs = {}
    for key in allowed_sorts:
        next_dirs[key] = "asc" if key == sort and direction == "desc" else "desc"

    return render(request, "paygo/paygo_sales.html", {
        "page_obj": page_obj,
        "stats": {STATUS_LABELS[k]: v for k, v in stats.items()},
        "search_query": search_query,
        "status_filter": status_filter,
        "current_sort": sort,
        "current_dir": direction,
        "next_dirs": next_dirs,
    })


def toggle_auto_paygo(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    settings, _ = PayGoSettings.objects.get_or_create(sale=sale)

    settings.auto_disable = not settings.auto_disable
    settings.save()

    return redirect("paygo_sales")