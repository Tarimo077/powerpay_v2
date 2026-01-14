from django.shortcuts import render, get_object_or_404
from django.utils.timezone import now, make_aware, is_naive
from .models import DeviceInfo
from .services.energy import (
    kwh_for_device,
    last_energy_timestamp
)
from django.core.paginator import Paginator
import requests
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.dateparse import parse_datetime

# ------------------------------
# Device List View
# ------------------------------
def device_list(request):
    devices = DeviceInfo.objects.all().order_by('deviceid')

    total_devices = devices.count()
    active_devices = devices.filter(active=True).count()
    inactive_devices = devices.filter(active=False).count()

    device_stats = []
    for d in devices:
        device_stats.append({
            "device": d,
            "last_seen": last_energy_timestamp(d),
            "kwh_today": kwh_for_device(
                d,
                now().replace(hour=0, minute=0, second=0, microsecond=0),
                now()
            )
        })

    paginator = Paginator(device_stats, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        "device_stats": page_obj.object_list,
        "page_obj": page_obj,

        # 👇 card stats
        "total_devices": total_devices,
        "active_devices": active_devices,
        "inactive_devices": inactive_devices,
    }

    return render(request, "devices/device_list.html", context)

# ------------------------------
# Device Detail / Stats
# ------------------------------
def device_detail(request, deviceid):
    device = get_object_or_404(DeviceInfo, deviceid=deviceid)

    start_of_day = now().replace(hour=0, minute=0, second=0, microsecond=0)

    kwh_today = kwh_for_device(device, start_of_day, now())

    context = {
        "device": device,
        "kwh_today": kwh_today,
        "last_seen": last_energy_timestamp(device),
    }
    return render(request, "devices/device_detail.html", context)


@login_required
def change_device_status(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    deviceid = request.POST.get("deviceid")
    if not deviceid:
        return HttpResponse("Device ID required", status=400)

    try:
        # 1️⃣ Parse current status
        current_status = request.POST.get("active", "false").lower() == "true"

        # 2️⃣ Call external API
        api_payload = {
            "selectedDev": deviceid,
            "status": not current_status
        }
        response = requests.post(
            "https://appliapay.com/changeStatus",
            json=api_payload,
            timeout=10
        )
        if response.status_code != 200:
            return HttpResponse("External API error", status=502)

        data = response.json()
        # Expected: {"selectedDev":"NEOPRS000001","status":false,"time":"2026-01-09T21:11:14.786000Z"}

        # 3️⃣ Extract updated info
        new_status = data.get("status", not current_status)
        updated_time_str = data.get("time")
        updated_time = None
        if updated_time_str:
            dt = parse_datetime(updated_time_str)
            if dt:
                updated_time = make_aware(dt) if is_naive(dt) else dt

        # 4️⃣ Build row context for HTMX partial
        start_of_day = now().replace(hour=0, minute=0, second=0, microsecond=0)

        
        device = get_object_or_404(DeviceInfo, deviceid=deviceid)
        kwh_today = kwh_for_device(device, start_of_day, now())
        row = {
            "deviceid": deviceid,
            "active": new_status,
            "last_seen": last_energy_timestamp(device),
            # If you want, you can calculate kWh today here too
            "kwh_today": kwh_today
        }

        return render(
            request,
            "partials/device-row.html",
            {
                "deviceid": row["deviceid"],
                "active": row["active"],
                "last_seen": row["last_seen"],
                "kwh_today": row["kwh_today"],
                "user": request.user
            }
        )

    except requests.exceptions.RequestException as e:
        return HttpResponse(f"API request failed: {e}", status=500)

    except Exception as e:
        return HttpResponse(f"Unexpected error: {e}", status=500)

