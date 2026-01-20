from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import TruncMonth
from customers.models import Customer


def customers_page(request):
    user = request.user
    is_superadmin = user.role == "superadmin"
    is_htmx = request.headers.get("HX-Request") == "true"

    # ---------------- BASE QUERYSET ----------------
    if is_superadmin:
        qs = Customer.objects.select_related("organization")
    else:
        qs = Customer.objects.filter(organization=user.organization)

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
                "next_dirs": next_dirs,  # ✅ already correct
            },
        )

    # ---------------- STATS ----------------
    total_customers = qs.count()

    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    new_customers_30 = qs.filter(date__date__gte=last_30_days).count()

    # ---------------- GENDER CHART ----------------
    gender_labels = []
    gender_data = []

    GENDER_MAP = {
        "F": "Female",
        "M": "Male",
        "O": "Other",
    }

    gender_qs = (
        Customer.objects
        .values("gender")
        .annotate(total=Count("id"))
    )

    gender_labels = [GENDER_MAP.get(x["gender"], "Unknown") for x in gender_qs]
    gender_data = [x["total"] for x in gender_qs]

    # ---------------- CUSTOMER GROWTH (MONTHLY) ----------------

    growth_qs = (
        Customer.objects
        .annotate(month=TruncMonth("date"))
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

        },
    )


def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    context = {
        "customer": customer
    }

    return render(request, "customers/customer_detail.html", context)