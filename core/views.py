from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from devices.models import DeviceInfo, DeviceData
from organizations.models import Organization
from devices.services.energy import (
    kwh_today_for_devices,
    kwh_this_month_for_devices,
)
from django.db.models import Sum
from datetime import datetime, timedelta
from transactions.models import Transaction  # your existing model


@login_required
def index(request):
    user = request.user
    is_superadmin = user.is_superuser or getattr(user, "role", "") == "admin"

    context = {"is_superadmin": is_superadmin}

    # ---------------- Organizations ----------------
    if is_superadmin:
        organizations = Organization.objects.all()
    else:
        organizations = [user.organization]

    # ---------------- Devices ----------------
    if is_superadmin:
        devices = DeviceInfo.objects.all()
    else:
        devices = DeviceInfo.objects.filter(organization=user.organization)
        

    # ---------------- Transactions ----------------
    if is_superadmin:
        transactions = Transaction.objects.all()
    else:
        transactions = Transaction.objects.filter(org=user.organization)

    # ---------------- Summary Cards ----------------
    context.update({
        "org_count": len(organizations),
        "device_count": devices.count(),
        "kwh_today": kwh_today_for_devices(devices),
        "kwh_month": kwh_this_month_for_devices(devices),
        "total_money": transactions.aggregate(total=Sum("amount"))["total"] or 0,
        "total_transactions": transactions.count(),
    })

    # ---------------- Device Status ----------------
    context["device_status_counts"] = {
        "ON": devices.filter(active=True).count(),
        "OFF": devices.filter(active=False).count(),
    }

    # ---------------- kWh Line Chart ----------------
    today = datetime.today().date()
    days = [today - timedelta(days=i) for i in reversed(range(7))]
    context["line_chart_labels"] = [d.strftime("%a %d") for d in days]

    line_chart_data = {}
    for device in devices:
        device_kwh = []
        for day in days:
            total = DeviceData.objects.filter(
                deviceid=device.deviceid,
                time__date=day
            ).aggregate(sum_kwh=Sum("kwh"))["sum_kwh"] or 0
            device_kwh.append(round(total, 2))
        if any(v > 0 for v in device_kwh):
            line_chart_data[device.deviceid] = device_kwh
    context["line_chart_data"] = line_chart_data

    # ---------------- Money by Org (superusers only) ----------------
    if is_superadmin:
        money_by_org = Transaction.objects.values('org__name').annotate(total=Sum('amount'))
        context['money_by_org_labels'] = [x['org__name'] for x in money_by_org]
        context['money_by_org_data'] = [float(x['total']) for x in money_by_org]

        # Money over last 7 days per org
        money_line_data = {}
        for org in organizations:
            daily_totals = []
            for day in days:
                total = Transaction.objects.filter(
                    org=org,
                    time__date=day
                ).aggregate(total=Sum('amount'))['total'] or 0
                daily_totals.append(float(total))
            money_line_data[org.name] = daily_totals
        context['money_line_data'] = money_line_data
        context['money_line_labels'] = [d.strftime("%a %d") for d in days]

    return render(request, "core/index.html", context)
