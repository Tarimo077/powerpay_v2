from datetime import datetime
from decimal import Decimal
from typing import Iterable, Dict, Optional
from django.db.models import Sum
from django.utils.timezone import make_aware, is_naive
from devices.models import DeviceInfo, DeviceData

# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------

def _aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware"""
    if is_naive(dt):
        return make_aware(dt)
    return dt

# ---------------------------------------------------------
# Core Calculations (DO NOT CHANGE)
# ---------------------------------------------------------

def kwh_for_device(device: DeviceInfo, start: datetime, end: datetime) -> Decimal:
    """Total kWh consumed by a single device (non-cumulative)."""
    start = _aware(start)
    end = _aware(end)

    agg = DeviceData.objects.filter(
        deviceid=device.deviceid,
        time__gte=start,
        time__lte=end,
    ).aggregate(total_kwh=Sum("kwh"))

    return Decimal(str(agg["total_kwh"] or 0))

# ---------------------------------------------------------
# Multi-device Aggregation (FIXED)
# ---------------------------------------------------------

def kwh_for_devices(
    devices: Iterable[DeviceInfo],
    start: datetime,
    end: datetime
) -> Dict[str, Decimal]:
    """Total kWh per device for multiple devices."""
    start = _aware(start)
    end = _aware(end)

    device_ids = [d.deviceid for d in devices]
    if not device_ids:
        return {}

    result = {deviceid: Decimal("0") for deviceid in device_ids}

    readings = (
        DeviceData.objects
        .filter(
            deviceid__in=device_ids,
            time__gte=start,
            time__lte=end,
        )
        .values("deviceid")
        .annotate(total_kwh=Sum("kwh"))
    )

    for row in readings:
        if row["total_kwh"] is not None:
            result[row["deviceid"]] = Decimal(str(row["total_kwh"]))

    return result

# ---------------------------------------------------------
# Time-Based Helpers
# ---------------------------------------------------------

def kwh_today_for_device(device: DeviceInfo) -> Decimal:
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return kwh_for_device(device, start, now)

def kwh_today_for_devices(devices: Iterable[DeviceInfo]) -> Decimal:
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return sum(
        kwh_for_devices(devices, start, now).values(),
        Decimal("0")
    )

def kwh_this_month_for_devices(devices: Iterable[DeviceInfo]) -> Decimal:
    now = datetime.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return sum(
        kwh_for_devices(devices, start, now).values(),
        Decimal("0")
    )

# ---------------------------------------------------------
# Debug / Validation Helpers
# ---------------------------------------------------------

def device_has_energy_data(device: DeviceInfo) -> bool:
    return DeviceData.objects.filter(deviceid=device.deviceid).exists()

def last_energy_timestamp(device: DeviceInfo) -> Optional[datetime]:
    return (
        DeviceData.objects
        .filter(deviceid=device.deviceid)
        .order_by("-time")
        .values_list("time", flat=True)
        .first()
    )
