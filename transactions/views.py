from django.core.paginator import Paginator
from django.db.models import Sum, Q, F, Value
from django.db.models.functions import Trim, Upper
from django.utils import timezone
from datetime import timedelta, datetime
from django.shortcuts import render
from .models import Transaction
from organizations.models import Organization


def transactions_page(request):
    user = request.user
    is_superadmin = user.role == "superadmin"

    # ------------------- Base Queryset -------------------
    if is_superadmin:
        qs = Transaction.objects.select_related('org').all()
    else:
        qs = Transaction.objects.filter(org=user.organization)

    qs = qs.order_by('-time')

    # ------------------- Stats -------------------
    last_7_days = timezone.now() - timedelta(days=7)
    stats = qs.aggregate(
        total_amount=Sum("amount"),
        last_7_days_amount=Sum(
            "amount",
            filter=Q(time__gte=last_7_days)
        ),
    )
    transaction_count = qs.count()

    # ------------------- Money by Org Pie Chart -------------------
    money_by_org_labels = []
    money_by_org_data = []

    if is_superadmin:
        # normalize org names and group by them
        money_by_org_qs = (
            qs
            .annotate(org_name=Upper(Trim(F('org__name'))))
            .values('org_name')
            .annotate(total=Sum('amount'))
            .order_by('org_name')
        )
        money_by_org_labels = [x['org_name'] for x in money_by_org_qs]
        money_by_org_data = [float(x['total']) for x in money_by_org_qs]

    # ------------------- Money Over Last 7 Days Line Chart -------------------
    days = [(timezone.now() - timedelta(days=i)).date() for i in reversed(range(7))]
    money_line_labels = [d.strftime('%a %d') for d in days]

    if is_superadmin:
        orgs = Organization.objects.all()
    else:
        orgs = [user.organization]

    money_line_data = {}
    for org in orgs:
        daily_totals = []
        for day in days:
            total = qs.filter(org=org, time__date=day).aggregate(total=Sum('amount'))['total'] or 0
            daily_totals.append(float(total))
        money_line_data[org.name] = daily_totals

    # ------------------- Pagination -------------------
    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ------------------- Assign colors for line chart -------------------
    import colorsys

    def get_colors(n):
        colors = []
        for i in range(n):
            hue = i / max(n, 1)
            rgb = colorsys.hsv_to_rgb(hue, 0.7, 0.5)
            colors.append('#%02x%02x%02x' % tuple(int(c * 255) for c in rgb))
        return colors

    org_colors = get_colors(len(money_line_data))

    context = {
        "page_obj": page_obj,
        "total_amount": stats['total_amount'] or 0,
        "last_7_days_amount": stats['last_7_days_amount'] or 0,
        "transaction_count": transaction_count,
        "is_superadmin": is_superadmin,
        "money_by_org_labels": money_by_org_labels,
        "money_by_org_data": money_by_org_data,
        "money_line_labels": money_line_labels,
        "money_line_data": money_line_data,
        "org_colors": org_colors,
    }

    return render(request, "transactions/transactions.html", context)
