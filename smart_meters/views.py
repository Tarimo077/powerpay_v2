from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Max, Sum
from .models import MeterReading

SMART_DB = "smart_meters"
LOCAL_TZ = ZoneInfo("Etc/GMT-3")  # UTC+3
ALLOWED_PAGE_SIZES = [10, 25, 50, 100]
MAX_CHART_POINTS = 500  # Maximum points for the chart


def parse_datetime(dt_str):
    """Safely parse datetime-local input"""
    if dt_str and dt_str not in ["None", ""]:
        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None
    return None


def meter_list(request):
    q = request.GET.get("q", "")
    sort = request.GET.get("sort", "meter_number")
    dir = request.GET.get("dir", "asc")
    page_size = int(request.GET.get("page_size", 10))
    if page_size not in ALLOWED_PAGE_SIZES:
        page_size = 10

    qs = MeterReading.objects.using(SMART_DB)
    if q:
        qs = qs.filter(meter_number__icontains=q)

    qs = qs.values("meter_number").annotate(
        latest_timestamp=Max("timestamp"),
        total_energy=Sum("energy_kwh")
    )

    qs = qs.filter(meter_number__isnull=False).exclude(meter_number="")

    # Convert timestamps to UTC+3
    for meter in qs:
        if meter["latest_timestamp"]:
            meter["latest_timestamp"] = meter["latest_timestamp"].replace(
                tzinfo=timezone.utc
            ).astimezone(LOCAL_TZ)

    allowed_sorts = ["meter_number", "latest_timestamp", "total_energy"]
    if sort not in allowed_sorts:
        sort = "meter_number"

    reverse = dir == "desc"
    qs = sorted(qs, key=lambda x: x[sort] if x[sort] is not None else 0, reverse=reverse)

    total_meters = len(qs)
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    
    context = {
        "page_obj": page_obj,
        "search_query": q,
        "current_sort": sort,
        "current_dir": dir,
        "page_size": page_size,
        "page_size_options": ALLOWED_PAGE_SIZES,
        "total_meters": total_meters,
    }
    return render(request, "smart_meters/meter_list.html", context)


def meter_detail(request, meter_number):
    start_date = parse_datetime(request.GET.get("start_date"))
    end_date = parse_datetime(request.GET.get("end_date"))
    page_size = int(request.GET.get("page_size", 10))
    if page_size not in ALLOWED_PAGE_SIZES:
        page_size = 10

    qs = MeterReading.objects.using(SMART_DB).filter(meter_number=meter_number)
    if start_date:
        qs = qs.filter(timestamp__gte=start_date)
    if end_date:
        qs = qs.filter(timestamp__lte=end_date)

    qs = qs.order_by("timestamp")  # ascending for chart

    # Convert timestamps to local timezone
    readings_sorted = []
    for r in qs:
        r.timestamp_local = r.timestamp.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
        readings_sorted.append(r)

    # Chart sampling to avoid overcrowding
    total_points = len(readings_sorted)
    step = max(1, total_points // MAX_CHART_POINTS)
    chart_sample = readings_sorted[::step]

    energy_labels = [r.timestamp_local.isoformat() for r in chart_sample]
    energy_data = [round(r.energy_kwh * 1000, 3) for r in chart_sample]  # Wh
    power_labels = energy_labels
    power_data = [round(r.power_kw * 1000, 3) for r in chart_sample]  # W

    # Table pagination
    paginator = Paginator(list(reversed(readings_sorted)), page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    total_readings = len(readings_sorted)
    last_reading = readings_sorted[-1] if readings_sorted else None
    last_kwh = last_reading.energy_kwh if last_reading else 0
    last_power = last_reading.power_kw if last_reading else 0

    context = {
        "meter_number": meter_number,
        "readings": page_obj,
        "page_obj": page_obj,
        "total_readings": total_readings,
        "last_kwh": last_kwh,
        "last_power": last_power,
        "energy_labels": energy_labels,
        "energy_data": energy_data,
        "power_labels": power_labels,
        "power_data": power_data,
        "start_date": start_date.isoformat() if start_date else "",
        "end_date": end_date.isoformat() if end_date else "",
        "page_size": page_size,
        "page_size_options": ALLOWED_PAGE_SIZES,
    }

    return render(request, "smart_meters/meter_detail.html", context)