from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone
from zoneinfo import ZoneInfo
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Max, Sum

from .models import MeterReading

SMART_DB = "smart_meters"
LOCAL_TZ = ZoneInfo("Africa/Nairobi")  # UTC+3
ALLOWED_PAGE_SIZES = [10, 25, 50, 100]
MAX_CHART_POINTS = 500


# -----------------------------
# SAFE DATETIME PARSER
# -----------------------------
def parse_datetime(dt_str):
    """
    Convert datetime-local (naive user input in EAT)
    → UTC for database filtering
    """
    if dt_str and dt_str not in ["None", ""]:
        try:
            dt = datetime.fromisoformat(dt_str)

            # treat input as LOCAL TIME (EAT)
            dt = dt.replace(tzinfo=LOCAL_TZ)

            # convert to UTC for DB query
            return dt.astimezone(dt_timezone.utc)

        except ValueError:
            return None
    return None


# -----------------------------
# METER LIST
# -----------------------------
def meter_list(request):
    q = request.GET.get("q", "")
    sort = request.GET.get("sort", "meter_number")
    direction = request.GET.get("dir", "asc")

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

    # -----------------------------
    # FIX: DISPLAY TIMEZONE
    # -----------------------------
    for meter in qs:
        if meter["latest_timestamp"]:
            ts = meter["latest_timestamp"]

            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=dt_timezone.utc)

            meter["latest_timestamp"] = ts.astimezone(LOCAL_TZ)

    allowed_sorts = ["meter_number", "latest_timestamp", "total_energy"]

    if sort not in allowed_sorts:
        sort = "meter_number"

    reverse = direction == "desc"

    qs = sorted(
        qs,
        key=lambda x: x[sort] if x[sort] is not None else 0,
        reverse=reverse
    )

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "smart_meters/meter_list.html", {
        "page_obj": page_obj,
        "search_query": q,
        "current_sort": sort,
        "current_dir": direction,
        "page_size": page_size,
        "page_size_options": ALLOWED_PAGE_SIZES,
        "total_meters": len(qs),
    })


# -----------------------------
# METER DETAIL
# -----------------------------
def meter_detail(request, meter_number):

    # -----------------------------
    # DATE RANGE HANDLING
    # -----------------------------
    start_date_raw = request.GET.get("start_date")
    end_date_raw = request.GET.get("end_date")

    start_date = parse_datetime(start_date_raw) if start_date_raw else None
    end_date = parse_datetime(end_date_raw) if end_date_raw else None

    # DEFAULT: last 24 hours
    if not start_date and not end_date:
        end_date = timezone.now()
        start_date = end_date - timedelta(hours=24)

    elif start_date and not end_date:
        end_date = timezone.now()

    elif end_date and not start_date:
        start_date = end_date - timedelta(hours=24)

    # -----------------------------
    # PAGINATION
    # -----------------------------
    page_size = int(request.GET.get("page_size", 10))
    if page_size not in ALLOWED_PAGE_SIZES:
        page_size = 10

    # -----------------------------
    # QUERYSET (DB = UTC)
    # -----------------------------
    qs = MeterReading.objects.using(SMART_DB).filter(
        meter_number=meter_number
    )

    if start_date:
        qs = qs.filter(timestamp__gte=start_date)

    if end_date:
        qs = qs.filter(timestamp__lte=end_date)

    qs = qs.order_by("timestamp")

    # -----------------------------
    # PROCESS READINGS (UTC → EAT)
    # -----------------------------
    readings_sorted = []

    for r in qs:
        ts = r.timestamp

        # ensure UTC-aware
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt_timezone.utc)

        r.timestamp_local = ts.astimezone(LOCAL_TZ)
        readings_sorted.append(r)

    # -----------------------------
    # CHART SAMPLING
    # -----------------------------
    total_points = len(readings_sorted)
    step = max(1, total_points // MAX_CHART_POINTS)
    chart_sample = readings_sorted[::step]

    energy_labels = [r.timestamp_local.isoformat() for r in chart_sample]
    #energy_data = [round(r.energy_kwh * 1000, 3) for r in chart_sample]

    power_labels = energy_labels
    #power_data = [round(r.power_kw * 1000, 3) for r in chart_sample]

    # -----------------------------
    # CHART DATA (FIXED FORMAT)
    # -----------------------------

    energy_data = [
        {
            "x": r.timestamp_local.isoformat(),
            "y": float(r.energy_kwh or 0) * 1000
        }
        for r in chart_sample
    ]

    power_data = [
        {
            "x": r.timestamp_local.isoformat(),
            "y": float(r.power_kw or 0) * 1000
        }
        for r in chart_sample
    ]

    # -----------------------------
    # TABLE PAGINATION
    # -----------------------------
    paginator = Paginator(list(reversed(readings_sorted)), page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    # -----------------------------
    # SUMMARY
    # -----------------------------
    total_readings = len(readings_sorted)

    last_reading = readings_sorted[-1] if readings_sorted else None
    last_kwh = last_reading.energy_kwh if last_reading else 0
    last_power = last_reading.power_kw if last_reading else 0

    # -----------------------------
    # DISPLAY RANGE (EAT)
    # -----------------------------
    start_local = start_date.astimezone(LOCAL_TZ) if start_date else None
    end_local = end_date.astimezone(LOCAL_TZ) if end_date else None

    return render(request, "smart_meters/meter_detail.html", {
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

        # UI FORMAT (EAT)
        "start_date": start_local.strftime("%Y-%m-%dT%H:%M") if start_local else "",
        "end_date": end_local.strftime("%Y-%m-%dT%H:%M") if end_local else "",

        "page_size": page_size,
        "page_size_options": ALLOWED_PAGE_SIZES,
    })