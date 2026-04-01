from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from sales.models import Sale
from transactions.models import Transaction
from devices.models import DeviceInfo
from .models import PayGoSettings
from .utils import get_payment_plan_details
from core.org_checker import get_accessible_organizations
from django.core.paginator import Paginator
from organizations.models import Organization
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json
import requests
from decouple import config


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
    mode = request.GET.get("mode", "")
    metered_filter = request.GET.get("metered", "")
    sort = request.GET.get("sort", "balance")
    direction = request.GET.get("dir", "desc")
    page = request.GET.get("page", 1)

    # -------- SALES BASE --------
    # -------- ACCESSIBLE ORGS --------
    if is_superadmin:
        accessible_orgs = Organization.objects.all()
    else:
        accessible_orgs = get_accessible_organizations(user)

    accessible_ids = list(accessible_orgs.values_list("id", flat=True))

    # -------- SALES BASE --------
    sales = Sale.objects.filter(
        purchase_mode="P",
        payment_plan__in=["Plan_1", "Plan_2"],
        organization_id__in=accessible_ids
    ).select_related("customer", "organization")

    today = timezone.now().date()

    # -------- PRELOAD TRANSACTIONS --------
    org_ids = sales.values_list("organization_id", flat=True)
    transactions = Transaction.objects.filter(
        org_id__in=org_ids
    ).values("ref", "org_id", "amount", "time", "txn_id")

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
        txns_sorted = sorted(txns, key=lambda x:x["time"], reverse=True)

        total_paid = sum(float(t["amount"]) for t in txns)
        last_payment = max((t["time"] for t in txns), default=None)

        # -------- PAYMENT LOGIC --------
        # Use sale.date as start
        start_date = sale.date.date() if sale.date else today
        weeks_elapsed = max((today - start_date).days // 7, 0)
        expected_paid = plan["deposit"] + (weeks_elapsed * plan["weekly_payment"])
        expected_paid = min(expected_paid, plan["total_price"])
        balance = max(plan["total_price"] - total_paid, 0)

        paygo_balance = total_paid - expected_paid
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

        prefix = "254"

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
            "metered": sale.metered,
            "paygo_balance": round(paygo_balance, 2),
            "transactions": txns_sorted,
            "contact": f"{prefix}{sale.customer.phone_number[-9:]}"
        }

        rows.append(row)

    # -------- SEARCH FILTER --------
    if search_query:
        rows = [r for r in rows if search_query.lower() in r["serial"].lower()
                or search_query.lower() in r["customer"].lower()]

    # -------- STATUS FILTER --------
    if status_filter:
        rows = [r for r in rows if r["status"] == status_filter]

    # -------- MODE FILTER --------
    if mode:
        # Directly assigns True if "auto", False otherwise
        rows = [r for r in rows if r.get("auto_disable") == (mode == "auto") and r.get("metered")]

    # -------- METERED FILTER --------
    if metered_filter:
        # Directly assigns True if "auto", False otherwise
        rows = [r for r in rows if r.get("metered") == (metered_filter == "yes")]

    # -------- STATS --------
    stats = {k: 0 for k in STATUS_LABELS.keys()}
    for r in rows:
        stats[r["status"]] += 1

    # -------- PAYGO METRICS --------
    total_receivable = 0
    receivable_at_risk = 0
    overdue_count = 0
    active_sales = 0

    for r in rows:
        total_receivable += r["balance"]

        if r["status"] in ["at_risk", "overdue"]:
            receivable_at_risk += r["balance"]

        if r["status"] == "overdue":
            overdue_count += 1

        if r["status"] != "fully_paid":
            active_sales += 1

    # -------- CHURN RATE --------
    churn_rate = 0
    if active_sales > 0:
        churn_rate = round((overdue_count / active_sales) * 100, 2)

    # -------- MONTH-ON-MONTH GROWTH --------
    #current_month = timezone.now().month
    #current_year = timezone.now().year

    #prev_month = current_month - 1 or 12
    #prev_year = current_year if current_month > 1 else current_year - 1

    #current_month_paid = 0
    #prev_month_paid = 0

    #for r in rows:
        #for txn in r["transactions"]:
            #if txn["time"]:
                #txn_date = txn["time"]

                #if txn_date.month == current_month and txn_date.year == current_year:
                    #current_month_paid += float(txn["amount"])

                #elif txn_date.month == prev_month and txn_date.year == prev_year:
                    #prev_month_paid += float(txn["amount"])

    #mom_growth = 0
    #if prev_month_paid > 0:
        #mom_growth = round(((current_month_paid - prev_month_paid) / prev_month_paid) * 100, 2)

    # -------- COLLECTION RATE --------
    total_expected = 0
    total_paid_all = 0

    for r in rows:
        total_paid_all += r["total_paid"]

        # reconstruct expected from paygo balance
        expected = r["total_paid"] - r["paygo_balance"]
        total_expected += max(expected, 0)

    collection_rate = 0
    if total_expected > 0:
        collection_rate = round((total_paid_all / total_expected) * 100, 2)

    # -------- SORTING --------
    allowed_sorts = {"balance": "balance", "paid": "total_paid", "serial": "serial", "customer": "customer", "paygo_balance": "paygo_balance"}
    sort_key = allowed_sorts.get(sort, "balance")
    reverse = direction == "desc"
    rows.sort(key=lambda x: x[sort_key], reverse=reverse)

    total_count = len(rows)

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
        "mode": mode,
        "current_sort": sort,
        "current_dir": direction,
        "next_dirs": next_dirs,
        "total_results": total_count,
        "metered_filter": metered_filter,
        # NEW METRICS
        "total_receivable": round(total_receivable, 2),
        "receivable_at_risk": round(receivable_at_risk, 2),
        "churn_rate": churn_rate,
        #"mom_growth": mom_growth,
        "collection_rate": collection_rate,
    })


def toggle_auto_paygo(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    settings, _ = PayGoSettings.objects.get_or_create(sale=sale)

    settings.auto_disable = not settings.auto_disable
    settings.save()

    return redirect("paygo_sales")

@login_required
@require_POST
def paygo_stk_push(request, sale_id):
    try:
        sale = Sale.objects.select_related("customer").get(id=sale_id)
    except Sale.DoesNotExist:
        return JsonResponse({"success": False, "error": "Sale not found"})

    try:
        data = json.loads(request.body)
        amount = float(data.get("amount"))
        contact = str(data.get("contact"))
    except Exception:
        return JsonResponse({"success": False, "error": "Invalid data"})

    # ✅ Normalize phone (force 254 format)
    if contact.startswith("0"):
        contact = "254" + contact[1:]
    elif contact.startswith("+"):
        contact = contact[1:]

    if not contact.startswith("254"):
        return JsonResponse({"success": False, "error": "Invalid phone format"})

    ref = sale.product_serial_number

    url = config('MPESA_ENDPOINT')

    payload = {
        "amount": int(amount),
        "contact": contact,
        "ref": ref
    }

    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()

        return JsonResponse({
            "success": True,
            "message": "STK push sent",
            "response": r.json() if "json" in r.headers.get("content-type", "") else r.text
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)
        })