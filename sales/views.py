from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from .models import Sale
from django.contrib.auth.decorators import login_required
from .forms import SaleForm
from notifications.utils import notify
from organizations.models import Organization
from core.org_utils import get_user_orgs, get_user_org_ids

@login_required
def sales_page(request):
    is_htmx = request.headers.get("HX-Request") == "true"
    search_query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "date")
    direction = request.GET.get("dir", "desc")
    is_superadmin = request.user.role == "superadmin"


    # ---------------- FILTERS ----------------
    period = request.GET.get("period", "all")
    org_filter = request.GET.get("org")
    purchase_mode = request.GET.get("mode")
    payment_plan = request.GET.get("plan")

    if org_filter in [None, "", "None"]:
        org_filter = None

    if purchase_mode in [None, "", "None"]:
        purchase_mode = None

    if payment_plan in [None, "", "None"]:
        payment_plan = None

    allowed_sorts = {
        "date": "date",
        "product_serial_number": "product_serial_number",
        "product_name": "product_name",
        "sales_rep": "sales_rep",
        "customer": "customer__name",
    }

    if sort not in allowed_sorts:
        sort = "date"
    if direction not in ("asc", "desc"):
        direction = "desc"

    order = f"-{allowed_sorts[sort]}" if direction == "desc" else allowed_sorts[sort]


    # ---------------- ACCESSIBLE ORGS ----------------
    accessible_orgs = get_user_orgs(request.user)
    accessible_ids = get_user_org_ids(request.user)

    # ---------------- BASE QUERYSET ----------------
    qs = Sale.objects.filter(
        organization_id__in=accessible_ids
    ).select_related("customer", "organization")

    # ---------------- ORGANIZATION FILTER ----------------
    if org_filter:
        try:
            org_filter = int(org_filter)
            if org_filter in accessible_ids:
                qs = qs.filter(organization_id=org_filter)
            else:
                org_filter = None  # prevent unauthorized access
        except:
            org_filter = None

    # ---------------- ORGANIZATIONS DROPDOWN ----------------
    organizations = accessible_orgs

    # ---------------- STATS ----------------
    total_sales = qs.count()
    paygo = qs.filter(purchase_mode="P").count()

    today = timezone.now()

    if period == "7d":
        qs = qs.filter(date__gte=today - timedelta(days=7))
    elif period == "30d":
        qs = qs.filter(date__gte=today - timedelta(days=30))
    elif period == "90d":
        qs = qs.filter(date__gte=today - timedelta(days=90))
    elif period == "1d":
        qs = qs.filter(date__gte=today - timedelta(days=1))
    elif period == "3d":
        qs = qs.filter(date__gte=today - timedelta(days=3))
    elif period == "14d":
        qs = qs.filter(date__gte=today - timedelta(days=14))
    elif period == "60d":
        qs = qs.filter(date__gte=today - timedelta(days=60))
    elif period == "180d":
        qs = qs.filter(date__gte=today - timedelta(days=180))
    elif period == "365d":
        qs = qs.filter(date__gte=today - timedelta(days=365))
    else:
        pass

    # ---------------- PURCHASE MODE ----------------
    if purchase_mode:
        qs = qs.filter(purchase_mode=purchase_mode)

    # ---------------- PAYMENT PLAN ----------------
    if purchase_mode == "P" and payment_plan:
        qs = qs.filter(payment_plan=payment_plan)

    if search_query:
        qs = qs.filter(
            Q(product_serial_number__icontains=search_query)
            | Q(product_name__icontains=search_query)
            | Q(sales_rep__icontains=search_query)
        )

    qs = qs.order_by(order)
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    table_fields = [
        ("date", "Date"),
        ("product_serial_number", "Serial Number"),
        ("product_name", "Product Name"),
        ("sales_rep", "Sales Rep"),
        ("customer", "Customer"),
    ]

    # Next sort directions
    next_dirs = {}
    for f, _ in table_fields:
        if f == sort:
            next_dirs[f] = "desc" if direction == "asc" else "asc"
        else:
            next_dirs[f] = "asc"

    

    # ---------------- MONTHLY SALES GROWTH (CUMULATIVE) ----------------
    monthly_qs = (
        qs
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )

    # Labels
    monthly_labels = [m["month"].strftime("%b %Y") for m in monthly_qs]

    # Compute cumulative totals
    monthly_data = []
    running_total = 0
    for m in monthly_qs:
        running_total += m["total"]
        monthly_data.append(running_total)

    # ---------------- PAYMENT OPTIONS DOUGHNUT ----------------
    # 1. Define the mapping for your labels
    MODE_MAPPING = {
        "C": "Cash",
        "P": "PayGo",
        "DA": "Deposit Account"
    }

    # 2. Query the database
    rep_qs = (
        qs
        .values("purchase_mode")
        .annotate(total=Count("id"))
        .order_by("purchase_mode")
    )

    # 3. Create labels and data, mapping the codes to full names
    # We use .get(code, code) so if a new code appears, it shows the raw code instead of crashing
    rep_labels = [MODE_MAPPING.get(r["purchase_mode"], r["purchase_mode"]) for r in rep_qs]
    rep_data = [r["total"] for r in rep_qs]

    # ---------------- HTMX TABLE ONLY ----------------
    if is_htmx:
        return render(
            request,
            "partials/sales_table.html",
            {
                "page_obj": page_obj,
                "fields": table_fields,
                "current_sort": sort,
                "current_dir": direction,
                "search_query": search_query,
                "next_dirs": next_dirs,
                "period": period,
                "org_filter": org_filter,
                "purchase_mode": purchase_mode,
                "payment_plan": payment_plan,
                "organizations": organizations,
                "is_superadmin": is_superadmin,

            },
        )

    # ---------------- FULL PAGE ----------------
    return render(
        request,
        "sales/sales.html",
        {
            "page_obj": page_obj,
            "fields": table_fields,
            "current_sort": sort,
            "current_dir": direction,
            "search_query": search_query,
            "next_dirs": next_dirs,
            "total_sales": total_sales,
            "total_paygo": paygo,
            "monthly_labels": monthly_labels,
            "monthly_data": monthly_data,
            "rep_labels": rep_labels,
            "rep_data": rep_data,
            "period": period,
            "org_filter": org_filter,
            "purchase_mode": purchase_mode,
            "payment_plan": payment_plan,
            "organizations": organizations,
            "is_superadmin": is_superadmin,
        },
    )


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    return render(
        request,
        "sales/sale_detail.html",
        {"sale": sale},
    )

@login_required
def sale_create(request):
    if request.method == "POST":
        form = SaleForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            notify(request.user, "New Sale", f"{form.cleaned_data['product_serial_number']}({form.cleaned_data['product_name']}) sale has been created.", "success")
            return redirect("sales_page")
    else:
        form = SaleForm(user=request.user)

    return render(request, "sales/sale_form.html", {
        "form": form,
        "title": "Add Sale"
    })

@login_required
def sale_update(request, pk):
    sale = get_object_or_404(Sale, pk=pk)

    if request.method == "POST":
        form = SaleForm(request.POST, instance=sale, user=request.user)
        if form.is_valid():
            form.save()
            notify(request.user, "Sale Updated", f"{sale.product_serial_number}({sale.product_name}) has been updated.", "info")
            return redirect("sales_page")
    else:
        form = SaleForm(instance=sale, user=request.user)

    return render(request, "sales/sale_form.html", {
        "form": form,
        "title": "Edit Sale"
    })

@login_required
def sale_delete(request, pk):
    sale = get_object_or_404(Sale, pk=pk)

    if request.method == "POST":
        sale.delete()
        notify(request.user, "Sale Deleted", f"{sale.product_serial_number}({sale.product_name}) has been deleted.", "warning")
        return redirect("sales_page")

    return redirect("sales_page")

