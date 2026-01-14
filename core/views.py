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

@login_required
def index(request):
    user = request.user
    is_superadmin = user.is_superuser or getattr(user, "role", "") == "admin"

    context = {"is_superadmin": is_superadmin}

    # ---------------- Get Devices & Organizations ----------------
    if is_superadmin:
        organizations = Organization.objects.all()
        devices = DeviceInfo.objects.all()
    else:
        organizations = [user.organization]
        devices = DeviceInfo.objects.all()  # adjust to user's allowed devices if needed

    context.update({
        "org_count": len(organizations),
        "device_count": devices.count(),
        "kwh_today": kwh_today_for_devices(devices),
        "kwh_month": kwh_this_month_for_devices(devices),
    })

    # ---------------- Device Status Pie Chart ----------------
    context["device_status_counts"] = {
        "ON": devices.filter(active=True).count(),
        "OFF": devices.filter(active=False).count(),
    }

    # ---------------- kWh Line Chart (Last 7 Days) ----------------
    today = datetime.today().date()
    days = [today - timedelta(days=i) for i in reversed(range(7))]
    line_chart_labels = [d.strftime("%a %d") for d in days]

    line_chart_data = {}
    for device in devices:
        device_kwh = []
        for day in days:
            total = DeviceData.objects.filter(
                deviceid=device.deviceid,
                time__date=day
            ).aggregate(sum_kwh=Sum("kwh"))["sum_kwh"] or 0
            device_kwh.append(round(total, 2))
        # Only include devices with any kWh > 0 in last 7 days
        if any(v > 0 for v in device_kwh):
            line_chart_data[device.deviceid] = device_kwh

    context["line_chart_labels"] = line_chart_labels
    context["line_chart_data"] = line_chart_data

    return render(request, "core/index.html", context)
