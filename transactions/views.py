from django.shortcuts import render
from django.core.cache import cache
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from .models import Transaction
from organizations.models import Organization
from django.utils import timezone
from datetime import timedelta


@login_required
def transactions_page(request):
    """
    Live table view for HTMX requests (search, sort, paginate)
    This ensures partial table works even if dashboard stats are cached
    """
    user = request.user
    is_superadmin = user.role == "superadmin" or user.is_superuser
    is_htmx = request.headers.get("HX-Request") == "true"

    # Base queryset
    if is_superadmin:
        qs = Transaction.objects.select_related("org")
    else:
        qs = Transaction.objects.filter(org=user.organization)

    # Search
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(ref__icontains=search_query)
            | Q(txn_id__icontains=search_query)
        )

    # ---------------- FILTERS ----------------
    period = request.GET.get("period", "all")
    org_filter = request.GET.get("org")

    if org_filter in [None, "", "None"]:
        org_filter = None

    # Organization filter (superadmin only)
    if is_superadmin and org_filter:
        qs = qs.filter(org_id=org_filter)

    # Date filter
    today = timezone.now()

    if period == "7d":
        qs = qs.filter(time__gte=today - timedelta(days=7))
    elif period == "30d":
        qs = qs.filter(time__gte=today - timedelta(days=30))
    elif period == "90d":
        qs = qs.filter(time__gte=today - timedelta(days=90))
    elif period == "1d":
        qs = qs.filter(time__gte=today - timedelta(days=1))
    elif period == "3d":
        qs = qs.filter(time__gte=today - timedelta(days=3))
    elif period == "14d":
        qs = qs.filter(time__gte=today - timedelta(days=14))
    elif period == "60d":
        qs = qs.filter(time__gte=today - timedelta(days=60))
    elif period == "180d":
        qs = qs.filter(time__gte=today - timedelta(days=180))
    elif period == "365d":
        qs = qs.filter(time__gte=today - timedelta(days=365))
    else:
        pass
    
    # Sorting
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
    sort_field = allowed_sorts.get(sort, "time")
    order = f"-{sort_field}" if direction == "desc" else sort_field
    qs = qs.order_by(order)

    organizations = Organization.objects.all() if is_superadmin else None
    total_results = qs.count()

    # Pagination
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    table_fields = [
        ("time", "Time"),
        ("name", "Name"),
        ("ref", "Reference"),
        ("txn_id", "Transaction ID"),
        ("amount", "Amount"),
    ]
    fields_with_dir = []
    for f, label in table_fields:
        next_dir = "desc" if (f == sort and direction == "asc") else "asc"
        fields_with_dir.append((f, label, next_dir))
    if is_superadmin:
        next_dir = "desc" if (sort == "org" and direction == "asc") else "asc"
        fields_with_dir.append(("org", "Organization", next_dir))

    # HTMX partial
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
                "period": period,
                "org_filter": org_filter,
                "organizations": organizations,
                "total_results": total_results
            },
        )

    # If normal page, include page_obj for table + cached stats
    context = cache.get("transaction_dashboard_superadmin" if is_superadmin else f"transaction_dashboard_org_{user.organization.id}") or {}
    context.update({
        "page_obj": page_obj,
        "fields_with_dir": fields_with_dir,
        "is_superadmin": is_superadmin,
        "current_sort": sort,
        "current_dir": direction,
        "search_query": search_query,
        "period": period,
        "org_filter": org_filter,
        "organizations": organizations,
        "total_results": total_results
    })

    return render(request, "transactions/transactions.html", context)