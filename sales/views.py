from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from .models import Sale
from django.contrib.auth.decorators import login_required

@login_required
def sales_page(request):
    is_htmx = request.headers.get("HX-Request") == "true"
    search_query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "date")
    direction = request.GET.get("dir", "desc")

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

    qs = Sale.objects.select_related("customer", "organization").order_by(order)

    if search_query:
        qs = qs.filter(
            Q(product_serial_number__icontains=search_query)
            | Q(product_name__icontains=search_query)
            | Q(sales_rep__icontains=search_query)
        )

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

    # ---------------- STATS ----------------
    total_sales = Sale.objects.count()
    last_30_days = timezone.now().date() - timedelta(days=30)
    new_sales_30 = Sale.objects.filter(date__gte=last_30_days).count()

    # ---------------- MONTHLY SALES GROWTH (CUMULATIVE) ----------------
    monthly_qs = (
        Sale.objects
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
        Sale.objects
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
            "new_sales_30": new_sales_30,
            "monthly_labels": monthly_labels,
            "monthly_data": monthly_data,
            "rep_labels": rep_labels,
            "rep_data": rep_data,
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
