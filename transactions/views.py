from django.shortcuts import render
from django.db.models import Sum, Q, F
from django.db.models.functions import TruncDate, Upper, Trim
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from organizations.models import Organization
from .models import Transaction


def transactions_page(request):
    user = request.user
    is_superadmin = user.role == "superadmin"
    is_htmx = request.headers.get("HX-Request") == "true"

    # ---------------- BASE QUERYSET ----------------
    if is_superadmin:
        base_qs = Transaction.objects.select_related("org")
    else:
        base_qs = Transaction.objects.filter(org=user.organization)

    qs = base_qs

    # ---------------- SEARCH ----------------
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(ref__icontains=search_query)
            | Q(txn_id__icontains=search_query)
        )

    # ---------------- SORTING ----------------
    allowed_sorts = {
        "time": "time",
        "name": "name",
        "ref": "ref",
        "amount": "amount",
        "txn_id": "txn_id",
        "org": "org__name",
    }

    sort = request.GET.get("sort", "time")
    direction = request.GET.get("dir", "desc")
    if sort not in allowed_sorts:
        sort = "time"
    if direction not in ("asc", "desc"):
        direction = "desc"

    order = f"-{allowed_sorts[sort]}" if direction == "desc" else allowed_sorts[sort]
    qs = qs.order_by(order)

    # ---------------- PAGINATION ----------------
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    table_fields = [
        ("time", "Time"),
        ("name", "Name"),
        ("ref", "Reference"),
        ("txn_id", "Transaction ID"),
        ("amount", "Amount"),
    ]

    # ---------------- NEXT SORT DIRECTIONS (Option 2) ----------------
    fields_with_dir = []
    for f, label in table_fields:
        next_dir = "desc" if (f == sort and direction == "asc") else "asc"
        fields_with_dir.append((f, label, next_dir))

    if is_superadmin:
        next_dir = "desc" if (sort == "org" and direction == "asc") else "asc"
        fields_with_dir.append(("org", "Organization", next_dir))

    # ---------------- HTMX TABLE ONLY ----------------
    if is_htmx:
        return render(
            request,
            "partials/transactions_table.html",
            {
                "page_obj": page_obj,
                "fields_with_dir": fields_with_dir,
                "is_superadmin": is_superadmin,
                "current_sort": sort,
                "current_dir": direction,
                "search_query": search_query,
            },
        )

    # ---------------- STATS ----------------
    today = timezone.now().date()
    date_list = [today - timedelta(days=i) for i in range(6, -1, -1)]
    start_date = date_list[0]

    stats = base_qs.aggregate(
        total_amount=Sum("amount"),
        last_7_days_amount=Sum("amount", filter=Q(time__date__gte=start_date)),
    )

    transaction_count = base_qs.count()

    # ---------------- PIE CHART (SUPERADMIN) ----------------
    money_by_org_labels = []
    money_by_org_data = []

    if is_superadmin:
        qs_org = (
            base_qs.annotate(org_name=Upper(Trim(F("org__name"))))
            .values("org_name")
            .annotate(total=Sum("amount"))
            .order_by("org_name")
        )
        money_by_org_labels = [x["org_name"] for x in qs_org]
        money_by_org_data = [float(x["total"]) for x in qs_org]

    # ---------------- LINE CHART (ALL ORGS) ----------------
    money_line_labels = [d.strftime("%d %b") for d in date_list]
    money_line_data = {}

    # 1. Initialize data for every organization
    if is_superadmin:
        all_orgs = base_qs.values_list("org__name", flat=True).distinct()
    else:
        all_orgs = [user.organization.name] if user.organization else []

    for name in all_orgs:
        money_line_data[name] = [0.0] * 7

    # 2. Query summed daily amounts for the last 7 days
    daily_org_qs = (
        base_qs.filter(time__date__gte=start_date)
        .annotate(day=TruncDate("time"))
        .values("org__name", "day")
        .annotate(total=Sum("amount"))
    )

    # 3. Fill the zero-lists with actual data
    date_to_idx = {date: i for i, date in enumerate(date_list)}
    for entry in daily_org_qs:
        name = entry["org__name"]
        day = entry["day"]
        total = float(entry["total"] or 0)
        if name in money_line_data and day in date_to_idx:
            idx = date_to_idx[day]
            money_line_data[name][idx] = total

    return render(
        request,
        "transactions/transactions.html",
        {
            "page_obj": page_obj,
            "fields_with_dir": fields_with_dir,
            "is_superadmin": is_superadmin,
            "total_amount": stats["total_amount"] or 0,
            "last_7_days_amount": stats["last_7_days_amount"] or 0,
            "transaction_count": transaction_count,
            "money_by_org_labels": money_by_org_labels,
            "money_by_org_data": money_by_org_data,
            "money_line_labels": money_line_labels,
            "money_line_data": money_line_data,
            "current_sort": sort,
            "current_dir": direction,
            "search_query": search_query,
        },
    )
