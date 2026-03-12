from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import TruncMonth
from customers.models import Customer
from sales.models import Sale
from django.contrib.auth.decorators import login_required
from .forms import CustomerForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from notifications.utils import notify
from organizations.models import Organization


@login_required
def customers_page(request):
    user = request.user
    is_superadmin = user.role == "superadmin"
    is_htmx = request.headers.get("HX-Request") == "true"

    # ---------------- BASE QUERYSET ----------------
    if is_superadmin:
        qs = Customer.objects.select_related("organization")
    else:
        qs = Customer.objects.filter(organization=user.organization)

    # ---------------- PERIOD FILTER ----------------
    period = request.GET.get("period", "all")

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


    # ---------------- ORGANIZATION FILTER ----------------
    org_filter = request.GET.get("org")

    if is_superadmin:
        organizations = Organization.objects.all()

        if org_filter:
            qs = qs.filter(organization_id=org_filter)

    else:
        organizations = None

    # ---------------- SEARCH ----------------
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(phone_number__icontains=search_query)
            | Q(id_number__icontains=search_query)
            | Q(location__icontains=search_query)
        )

    # ---------------- SORTING ----------------
    allowed_sorts = {
        "name": "name",
        "phone": "phone_number",
        "location": "location",
        "gender": "gender",
        "household_size": "household_size",
        "date": "date",
        "org": "organization__name",
    }

    sort = request.GET.get("sort", "date")
    direction = request.GET.get("dir", "desc")

    if sort not in allowed_sorts:
        sort = "date"
    if direction not in ("asc", "desc"):
        direction = "desc"

    order = f"-{allowed_sorts[sort]}" if direction == "desc" else allowed_sorts[sort]
    qs = qs.order_by(order)

    # ---------------- PAGINATION ----------------
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    table_fields = [
        ("name", "Name"),
        ("phone", "Phone"),
        ("location", "Location"),
        ("gender", "Gender"),
        ("household_size", "Household Size"),
        ("date", "Created"),
    ]

    # ---------------- NEXT SORT DIRECTIONS ----------------
    next_dirs = {}
    all_fields = [f for f, _ in table_fields]
    if is_superadmin:
        all_fields.append("org")

    for f in all_fields:
        if f == sort:
            next_dirs[f] = "desc" if direction == "asc" else "asc"
        else:
            next_dirs[f] = "asc"

    # ---------------- HTMX TABLE ONLY ----------------
    if is_htmx:
        return render(
            request,
            "partials/customers_table.html",
            {
                "page_obj": page_obj,
                "fields": table_fields,
                "is_superadmin": is_superadmin,
                "current_sort": sort,
                "current_dir": direction,
                "search_query": search_query,
                "next_dirs": next_dirs,
                "period": period,
                "org_filter": org_filter,
                "organizations": organizations,
            },
        )

    # ---------------- STATS ----------------
    total_customers = qs.count()

    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    new_customers_30 = qs.filter(date__date__gte=last_30_days).count()

    # ---------------- GENDER CHART (REFACTORED) ----------------
    GENDER_MAP = {
        "F": "Female",
        "M": "Male",
        "O": "Other",
    }

    # IMPORTANT: .order_by() clears previous sorting to allow proper GROUP BY
    gender_qs = (
        qs.order_by()
        .values("gender")
        .annotate(total=Count("id"))
    )

    gender_labels = []
    gender_data = []

    for item in gender_qs:
        label = GENDER_MAP.get(item["gender"]) or "Unknown"
        # If multiple DB values map to 'Unknown' (like None and ""), combine them
        if label in gender_labels:
            idx = gender_labels.index(label)
            gender_data[idx] += item["total"]
        else:
            gender_labels.append(label)
            gender_data.append(item["total"])

    # ---------------- CUSTOMER GROWTH (MONTHLY) ----------------
    growth_qs = (
        qs.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    customer_growth_labels = []
    customer_growth_data = []

    running_total = 0
    for row in growth_qs:
        running_total += row["count"]
        customer_growth_labels.append(row["month"].strftime("%b %Y"))
        customer_growth_data.append(running_total)

    return render(
        request,
        "customers/customers.html",
        {
            "page_obj": page_obj,
            "fields": table_fields,
            "is_superadmin": is_superadmin,
            "total_customers": total_customers,
            "new_customers_30": new_customers_30,
            "gender_labels": gender_labels,
            "gender_data": gender_data,
            "current_sort": sort,
            "current_dir": direction,
            "search_query": search_query,
            "next_dirs": next_dirs,  
            "customer_growth_labels": customer_growth_labels,
            "customer_growth_data": customer_growth_data,
            "period": period,
            "org_filter": org_filter,
            "organizations": organizations,
        },
    )


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    # ---- SALES TABLE LOGIC ----
    search_query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "date")
    direction = request.GET.get("dir", "desc")

    allowed_sorts = {
        "date": "date",
        "product": "product_name",
        "serial": "product_serial_number",
        "sales_rep": "sales_rep",
    }

    if sort not in allowed_sorts:
        sort = "date"
    if direction not in ("asc", "desc"):
        direction = "desc"

    order = f"-{allowed_sorts[sort]}" if direction == "desc" else allowed_sorts[sort]

    sales_qs = (
        Sale.objects
        .filter(customer=customer)
        .order_by(order)
    )

    if search_query:
        sales_qs = sales_qs.filter(
            Q(product_name__icontains=search_query)
            | Q(product_serial_number__icontains=search_query)
            | Q(sales_rep__icontains=search_query)
        )

    paginator = Paginator(sales_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    table_fields = [
        ("date", "Date"),
        ("product", "Product Name"),
        ("serial", "Serial Number"),
        ("sales_rep", "Sales Rep"),
    ]

    next_dirs = {}
    for f, _ in table_fields:
        if f == sort:
            next_dirs[f] = "desc" if direction == "asc" else "asc"
        else:
            next_dirs[f] = "asc"

    context = {
        "customer": customer,
        "page_obj": page_obj,
        "fields": table_fields,
        "current_sort": sort,
        "current_dir": direction,
        "search_query": search_query,
        "next_dirs": next_dirs,
    }

    # HTMX → return only the table
    if request.headers.get("HX-Request"):
        return render(
            request,
            "partials/customer_sales_table.html",
            context,
        )

    return render(request, "customers/customer_detail.html", context)


@login_required
def customer_create(request):
    if request.method == "POST":
        form = CustomerForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            notify(request.user, "New Customer", f"{form.cleaned_data['name']} has been added as a customer.", "info")
            return redirect("customers_page")
    else:
        form = CustomerForm(user=request.user)

    return render(request, "customers/customer_form.html", {
        "form": form,
        "title": "Add Customer"
    })



@login_required
def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)

    if form.is_valid():
        form.save()
        notify(request.user, "Customer Update", f"{customer.name}'s details have been updated.", "info")
        return redirect("customer_detail", pk=pk)

    return render(request, "customers/customer_form.html", {
        "form": form,
        "title": "Edit Customer",
        "customer": customer,
    })

@login_required
@require_POST
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer.delete()
    notify(request.user, "Customer Deleted", f"{customer.name} has been deleted as a customer.", "warning")
    return JsonResponse({"success": True})