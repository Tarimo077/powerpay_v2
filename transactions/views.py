from django.shortcuts import render
from django.core.cache import cache
from django.db.models import Q, F, Sum
from django.db.models.functions import TruncDate, Upper, Trim
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from .models import Transaction
from core.tasks import cache_transaction_dashboard_for_org, cache_transaction_dashboard_superadmin

@login_required
def transactions_index(request):
    """
    Dashboard-like view for transactions:
    - Uses cached stats for summary/line/pie charts
    - HTMX table remains live (paginated queryset) and unaffected
    """
    user = request.user
    is_superadmin = user.role in ("superadmin", "admin") or user.is_superuser

    # Determine cache key
    if is_superadmin:
        cache_key = "transaction_dashboard_superadmin"
    else:
        cache_key = f"transaction_dashboard_org_{user.organization.id}"

    # Get cached stats
    context = cache.get(cache_key)

    if context:
        return render(request, "transactions/transactions.html", context)

    # Cache missing → trigger rebuild
    if is_superadmin:
        cache_transaction_dashboard_superadmin.delay()
    else:
        cache_transaction_dashboard_for_org.delay(user.organization.id)

    # Loading page while stats are rebuilt
    return render(request, "core/loading.html")


@login_required
def transactions_page(request):
    """
    Live table view for HTMX requests (search, sort, paginate)
    This ensures partial table works even if dashboard stats are cached
    """
    user = request.user
    is_superadmin = user.role in ("superadmin", "admin") or user.is_superuser
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
    })

    return render(request, "transactions/transactions.html", context)