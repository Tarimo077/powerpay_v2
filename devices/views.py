from django.shortcuts import render, get_object_or_404
from django.utils.timezone import now, make_aware, is_naive
from .models import DeviceInfo, DeviceData
from .services.energy import (
    kwh_for_device,
    last_energy_timestamp
)
from django.core.paginator import Paginator
import requests
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum 


COOKING_GAP_SECONDS = 20 * 60  # 20 minutes
# ------------------------------
# Device List View
# ------------------------------
@login_required
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

@login_required
def device_detail(request, deviceid):
    device = get_object_or_404(DeviceInfo, deviceid=deviceid)

    # ---------------------------
    # ALL readings (for cooking events + last seen)
    # ---------------------------
    all_readings = DeviceData.objects.filter(deviceid=deviceid).order_by("time")
    last_seen = (
        timezone.localtime(all_readings.last().time)
        if all_readings.exists()
        else None
    )

    # ---------------------------
    # Cooking Event Detection (ALL TIME)
    # ---------------------------
    cooking_events = []
    current_event = []
    prev_time = None

    for r in all_readings:
        if prev_time:
            gap = (r.time - prev_time).total_seconds()
            if gap > COOKING_GAP_SECONDS:
                if current_event:
                    cooking_events.append(current_event)
                current_event = []
        current_event.append(r)
        prev_time = r.time

    if current_event:
        cooking_events.append(current_event)

    # ---------------------------
    # Cooking Event Metrics (ALL TIME)
    # ---------------------------
    cooking_event_rows = []
    total_cooking_time_minutes = 0
    total_cooking_time_7d_minutes = 0
    seven_days_ago = timezone.now() - timedelta(days=7)

    for idx, event in enumerate(cooking_events, start=1):
        start_time = timezone.localtime(event[0].time)
        end_time = timezone.localtime(event[-1].time)
        duration_minutes = (end_time - start_time).total_seconds() / 60
        energy_kwh = sum(float(r.kwh or 0) for r in event)

        total_cooking_time_minutes += duration_minutes
        if end_time >= seven_days_ago:
            total_cooking_time_7d_minutes += duration_minutes

        cooking_event_rows.append({
            "index": idx,
            "start": start_time,
            "end": end_time,
            "duration": round(duration_minutes, 1),
            "energy": round(energy_kwh, 3),
        })

    # ---------------------------
    # Cooking Events Counts
    # ---------------------------
    cooking_events_all_time = len(cooking_events)
    cooking_events_7d = sum(
        1 for e in cooking_events
        if timezone.localtime(e[0].time) >= seven_days_ago
    )

    #------------------------------------------
    # Sorting Logic
    #------------------------------------------
        # ---------------------------
    # SORTING (Cooking Events Table)
    # ---------------------------
    sort = request.GET.get("sort", "start")
    direction = request.GET.get("dir", "desc")

    allowed_sorts = {
        "start": "start",
        "end": "end",
        "duration": "duration",
        "energy": "energy",
    }

    if sort not in allowed_sorts:
        sort = "start"
    if direction not in ("asc", "desc"):
        direction = "desc"

    reverse = direction == "desc"
    cooking_event_rows.sort(
        key=lambda x: x[allowed_sorts[sort]],
        reverse=reverse,
    )

    # Next sort directions
    next_dirs = {}
    for key in allowed_sorts.keys():
        if key == sort:
            next_dirs[key] = "desc" if direction == "asc" else "asc"
        else:
            next_dirs[key] = "asc"

    # ---------------------------
    # Pagination for cooking events table
    # ---------------------------
    paginator = Paginator(cooking_event_rows, 10)  # 10 per page
    page_number = request.GET.get("page")
    cooking_event_rows_paginated = paginator.get_page(page_number)

    # ---------------------------
    # LAST 7 DAYS DATA (Charts)
    # ---------------------------
    readings_7d = DeviceData.objects.filter(deviceid=deviceid, time__gte=seven_days_ago).order_by("time")
    total_kwh_7d = readings_7d.aggregate(total=Sum("kwh"))["total"] or 0
    total_kwh = all_readings.aggregate(total=Sum("kwh"))["total"] or 0

    # Energy per day (aggregated kWh)
    daily_energy = {}
    for r in readings_7d:
        day = timezone.localtime(r.time).date()
        daily_energy[day] = daily_energy.get(day, 0) + float(r.kwh or 0)

    last_7_days = [timezone.localdate() - timedelta(days=i) for i in reversed(range(7))]
    energy_labels = [d.strftime("%a") for d in last_7_days]
    energy_data = [round(daily_energy.get(d, 0), 3) for d in last_7_days]

    # Cooking events per day (last 7 days)
    daily_events = {}
    for event in cooking_events:
        day = timezone.localtime(event[0].time).date()
        if day in last_7_days:
            daily_events[day] = daily_events.get(day, 0) + 1

    cooking_event_labels = energy_labels
    cooking_event_data = [daily_events.get(d, 0) for d in last_7_days]

    #---------------------------
    #HTMX
    #---------------------------
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "partials/cooking_events_table.html",
            {
                "cooking_event_rows": cooking_event_rows_paginated,
                "current_sort": sort,
                "current_dir": direction,
                "next_dirs": next_dirs,
                "device": device,
            },
        )

    # ---------------------------
    # Context
    # ---------------------------
    context = {
        "device": device,
        "last_seen": last_seen,

        # Cooking events counts
        "cooking_events_today": cooking_events_all_time,  # all-time total
        "cooking_events_7d": cooking_events_7d,          # last 7 days

        # Cooking time
        "total_cooking_time": round(total_cooking_time_minutes, 1),      # all-time in minutes
        "cooking_time_7d": round(total_cooking_time_7d_minutes, 1),      # last 7 days in minutes

        # Energy
        "total_kwh_7d": round(total_kwh_7d, 3),
        "total_kwh": round(total_kwh, 3),
        "energy_labels": energy_labels,
        "energy_data": energy_data,

        # Cooking events chart
        "cooking_event_labels": cooking_event_labels,
        "cooking_event_data": cooking_event_data,

        # Table
        "cooking_event_rows": cooking_event_rows_paginated,

        #Sort vars
        "current_sort": sort,
        "current_dir": direction,
        "next_dirs": next_dirs,

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

@login_required
def change_device_status_partial(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    deviceid = request.POST.get("deviceid")
    if not deviceid:
        return HttpResponse("Device ID required", status=400)

    try:
        # Parse current toggle state
        current_status = request.POST.get("active", "false").lower() == "true"

        # Call external API to toggle device
        api_payload = {"selectedDev": deviceid, "status": not current_status}
        response = requests.post(
            "https://appliapay.com/changeStatus",
            json=api_payload,
            timeout=10
        )
        if response.status_code != 200:
            return HttpResponse("External API error", status=502)

        data = response.json()
        # {"selectedDev":"NEOPRS000001","status":false,"time":"2026-01-09T21:11:14.786000Z"}

        # Extract new status
        new_status = data.get("status", not current_status)

        # Optional: parse last seen from API
        updated_time_str = data.get("time")
        updated_time = None
        if updated_time_str:
            dt = parse_datetime(updated_time_str)
            if dt:
                updated_time = make_aware(dt) if is_naive(dt) else dt

        # Fetch device from DB
        device = get_object_or_404(DeviceInfo, deviceid=deviceid)
        device.active = new_status
        device.save(update_fields=["active"])

        # Render partial
        return render(
            request,
            "partials/device_status_partial.html",
            {
                "device": device,
            }
        )

    except requests.exceptions.RequestException as e:
        return HttpResponse(f"API request failed: {e}", status=500)

    except Exception as e:
        return HttpResponse(f"Unexpected error: {e}", status=500)
