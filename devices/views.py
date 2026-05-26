from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now, make_aware, is_naive
from .services.energy import (
    kwh_for_device,
    last_energy_timestamp
)
from django.core.paginator import Paginator
import requests
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Q, OuterRef, Subquery
from notifications.utils import notify
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from .services.device_api import call_change_status_api
from organizations.models import Organization
from core.org_checker import get_accessible_organizations
from inventory.models import InventoryItem
from django.db import transaction
from django.db import transaction
from django.utils import timezone
from .models import (
    DeviceInfo,
    DeviceData,
    DeviceCommandSchedule,
    TrackKwh,
    DeviceTestingBatch,
    DeviceTestingBatchItem,
    DeviceBatchDispatch,
)
from .forms import (
    DeviceTestingBatchForm,
    DeviceBatchDispatchForm,
    DeviceForm, 
    DeviceCommandScheduleForm, 
    BulkDeviceCreateForm
)

COOKING_GAP_SECONDS = 20 * 60  # 20 minutes

def is_superadmin(user):
    return user.is_superuser or getattr(user, "role", None) == "superadmin"


def _accessible_testing_batch_queryset(user):
    """
    Test batches no longer belong to an organization directly.
    Superadmins can see all batches.
    Other users can see batches they created or batches containing devices
    from organizations they can access.
    """
    qs = DeviceTestingBatch.objects.select_related("created_by")

    if is_superadmin(user):
        return qs.distinct()

    accessible_orgs = get_accessible_organizations(user)

    return (
        qs.filter(
            Q(created_by=user)
            | Q(items__device__organization__in=accessible_orgs)
            | Q(items__device__organizations__in=accessible_orgs)
        )
        .distinct()
    )


@login_required
def testing_batch_list(request):
    batches = _accessible_testing_batch_queryset(request.user)

    return render(
        request,
        "devices/testing_batch_list.html",
        {
            "batches": batches,
        },
    )


@login_required
def testing_batch_create(request):
    if request.method == "POST":
        form = DeviceTestingBatchForm(request.POST, user=request.user)

        if form.is_valid():
            with transaction.atomic():
                batch = form.save(commit=False)
                batch.created_by = request.user
                batch.save()

                selected_devices = form.cleaned_data["devices"]

                DeviceTestingBatchItem.objects.bulk_create([
                    DeviceTestingBatchItem(
                        batch=batch,
                        device=device,
                    )
                    for device in selected_devices
                ])

                batch.refresh_status()

            notify(
                request.user,
                "Testing Batch Created",
                f"{batch.name} has been created with {selected_devices.count()} device(s).",
                "success",
            )

            return redirect("devices:testing_batch_detail", pk=batch.pk)
    else:
        form = DeviceTestingBatchForm(user=request.user)

    return render(
        request,
        "devices/testing_batch_form.html",
        {
            "form": form,
        },
    )


@login_required
def testing_batch_detail(request, pk):
    batch = get_object_or_404(
        _accessible_testing_batch_queryset(request.user),
        pk=pk,
    )

    items = (
        DeviceTestingBatchItem.objects
        .select_related("device", "tested_by")
        .filter(batch=batch)
        .order_by("device__deviceid")
    )

    return render(
        request,
        "devices/testing_batch_detail.html",
        {
            "batch": batch,
            "items": items,
        },
    )


@login_required
def testing_batch_update_results(request, pk):
    batch = get_object_or_404(
        _accessible_testing_batch_queryset(request.user),
        pk=pk,
    )

    if batch.status == DeviceTestingBatch.STATUS_DISPATCHED:
        notify(
            request.user,
            "Batch Locked",
            "This batch has already been dispatched and can no longer be edited.",
            "warning",
        )
        return redirect("devices:testing_batch_detail", pk=batch.pk)

    if request.method != "POST":
        return redirect("devices:testing_batch_detail", pk=batch.pk)

    item_ids = request.POST.getlist("item_id")
    test_one_ids = set(request.POST.getlist("test_one_passed"))
    test_two_ids = set(request.POST.getlist("test_two_passed"))
    packed_ids = set(request.POST.getlist("packed"))

    current_time = timezone.now()

    with transaction.atomic():
        items = list(
            DeviceTestingBatchItem.objects
            .select_for_update()
            .filter(batch=batch, id__in=item_ids)
        )

        for item in items:
            item_id = str(item.id)

            old_test_one = item.test_one_passed
            old_test_two = item.test_two_passed
            old_packed = item.packed

            item.test_one_passed = item_id in test_one_ids
            item.test_two_passed = item_id in test_two_ids

            requested_packed = item_id in packed_ids
            item.packed = requested_packed and item.test_one_passed and item.test_two_passed

            item.test_one_notes = request.POST.get(f"test_one_notes_{item.id}", "").strip()
            item.test_two_notes = request.POST.get(f"test_two_notes_{item.id}", "").strip()
            item.packing_notes = request.POST.get(f"packing_notes_{item.id}", "").strip()

            if (
                item.test_one_passed != old_test_one
                or item.test_two_passed != old_test_two
            ):
                item.tested_by = request.user
                item.tested_at = current_time

            if item.packed and not old_packed:
                item.packed_at = current_time

            if not item.packed:
                item.packed_at = None

            item.save()

        batch.refresh_status()

    notify(
        request.user,
        "Batch Updated",
        f"{batch.name} test and packing results have been saved.",
        "success",
    )

    return redirect("devices:testing_batch_detail", pk=batch.pk)


@login_required
def testing_batch_dispatch(request, pk):
    batch = get_object_or_404(
        _accessible_testing_batch_queryset(request.user),
        pk=pk,
    )

    if batch.status == DeviceTestingBatch.STATUS_DISPATCHED:
        return redirect("devices:testing_batch_dispatch_detail", pk=batch.pk)

    batch.refresh_status()

    if not batch.is_ready_for_dispatch:
        notify(
            request.user,
            "Batch Not Ready",
            "All devices must pass Test 1, pass Test 2, and be packed before dispatch.",
            "warning",
        )
        return redirect("devices:testing_batch_detail", pk=batch.pk)

    if request.method == "POST":
        form = DeviceBatchDispatchForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                dispatch = form.save(commit=False)
                dispatch.batch = batch
                dispatch.dispatched_by = request.user
                dispatch.save()

                batch.status = DeviceTestingBatch.STATUS_DISPATCHED
                batch.save(update_fields=["status", "updated_at"])

            notify(
                request.user,
                "Batch Dispatched",
                f"{batch.name} has been dispatched by {request.user}.",
                "success",
            )

            return redirect("devices:testing_batch_dispatch_detail", pk=batch.pk)
    else:
        form = DeviceBatchDispatchForm()

    return render(
        request,
        "devices/testing_batch_dispatch.html",
        {
            "batch": batch,
            "form": form,
        },
    )


@login_required
def testing_batch_dispatch_detail(request, pk):
    batch = get_object_or_404(
        _accessible_testing_batch_queryset(request.user),
        pk=pk,
    )

    items = (
        DeviceTestingBatchItem.objects
        .select_related("device")
        .filter(batch=batch)
        .order_by("device__deviceid")
    )

    dispatch = getattr(batch, "dispatch", None)

    return render(
        request,
        "devices/testing_batch_dispatch_detail.html",
        {
            "batch": batch,
            "items": items,
            "dispatch": dispatch,
        },
    )


@login_required
def testing_batch_delete(request, pk):
    batch = get_object_or_404(
        _accessible_testing_batch_queryset(request.user),
        pk=pk,
    )

    if request.method == "POST":
        batch_name = batch.name

        with transaction.atomic():
            batch.delete()

        notify(
            request.user,
            "Testing Batch Deleted",
            f"{batch_name} and its related testing records have been deleted.",
            "success",
        )

        return redirect("devices:testing_batch_list")

    return render(
        request,
        "devices/testing_batch_confirm_delete.html",
        {
            "batch": batch,
        },
    )

def _user_is_device_admin(user):
    return user.is_superuser or getattr(user, "role", None) == "superadmin"


def _accessible_device_queryset(user):
    """
    Returns devices accessible to the user.

    Important:
    We check BOTH:
    1. device.organizations M2M relationship
    2. legacy device.organization_id

    This keeps old devices visible even if they have not yet been backfilled
    into devactivity_organizations.
    """
    if _user_is_device_admin(user):
        accessible_orgs = Organization.objects.all()
    else:
        accessible_orgs = get_accessible_organizations(user)

    accessible_ids = list(accessible_orgs.values_list("id", flat=True))

    if _user_is_device_admin(user):
        devices = (
            DeviceInfo.objects
            .all()
            .select_related("organization")
            .prefetch_related("organizations")
            .distinct()
        )
    else:
        devices = (
            DeviceInfo.objects
            .filter(
                Q(organizations__id__in=accessible_ids) |
                Q(organization_id__in=accessible_ids)
            )
            .select_related("organization")
            .prefetch_related("organizations")
            .distinct()
        )

    return devices, accessible_orgs, accessible_ids


def _accessible_device_or_404(user, deviceid):
    devices, _, _ = _accessible_device_queryset(user)
    return get_object_or_404(devices, deviceid=deviceid)


# ------------------------------
# Device List View
# ------------------------------

@login_required
def device_list(request):
    user = request.user
    q = request.GET.get("q", "")
    status = request.GET.get("status", "all")
    org_id = request.GET.get("org")

    if org_id in [None, "", "None"]:
        org_id = None

    # -------- ACCESSIBLE ORGS --------
    devices, accessible_orgs, accessible_ids = _accessible_device_queryset(user)
    is_admin = _user_is_device_admin(user)

    # -------- ORG FILTER --------
    if org_id and org_id.isdigit():
        org_id = int(org_id)

        if org_id in accessible_ids:
            devices = devices.filter(
                Q(organizations__id=org_id) |
                Q(organization_id=org_id)
            ).distinct()
        else:
            org_id = None
    else:
        org_id = None

    organizations = accessible_orgs

    # Search
    if q:
        devices = devices.filter(deviceid__icontains=q)

    # Status filter
    if status == "active":
        devices = devices.filter(active=True)
    elif status == "inactive":
        devices = devices.filter(active=False)

    # -------- SORTING --------
    # ``last_seen`` comes from the latest DeviceData row, so annotate it here
    # before pagination. That keeps sorting consistent across all pages.
    last_seen_subquery = (
        DeviceData.objects
        .filter(deviceid=OuterRef("deviceid"))
        .order_by("-time")
        .values("time")[:1]
    )

    devices = devices.annotate(last_seen_for_sort=Subquery(last_seen_subquery))

    allowed_sorts = {
        "deviceid": "deviceid",
        "status": "active",
        "last_seen": "last_seen_for_sort",
        "main_org": "organization__name",
    }

    sort = request.GET.get("sort", "deviceid")
    direction = request.GET.get("dir", "asc")

    if sort not in allowed_sorts:
        sort = "deviceid"
    if direction not in ("asc", "desc"):
        direction = "asc"

    order_field = allowed_sorts[sort]
    order = f"-{order_field}" if direction == "desc" else order_field
    devices = devices.order_by(order, "deviceid").distinct()

    next_dirs = {}
    for field in allowed_sorts:
        next_dirs[field] = "desc" if (field == sort and direction == "asc") else "asc"

    allowed_page_sizes = [10, 25, 50, 100]
    try:
        page_size = int(request.GET.get("page_size", 10))
    except (TypeError, ValueError):
        page_size = 10

    if page_size not in allowed_page_sizes:
        page_size = 10

    # Stats
    total_devices = devices.count()
    active_devices = devices.filter(active=True).distinct().count()
    inactive_devices = devices.filter(active=False).distinct().count()

    device_stats = [
        {
            "device": d,
            "last_seen": d.last_seen_for_sort,
            "organizations": d.organizations.all(),
        }
        for d in devices
    ]

    paginator = Paginator(device_stats, page_size)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "device_stats": page_obj.object_list,
        "search_query": q,
        "status_filter": status,
        "org_filter": org_id,
        "organizations": organizations,
        "is_admin": is_admin,
        "is_superuser": is_admin,
        "total_devices": total_devices,
        "active_devices": active_devices,
        "inactive_devices": inactive_devices,
        "page_size": page_size,
        "page_size_options": allowed_page_sizes,
        "current_sort": sort,
        "current_dir": direction,
        "next_dirs": next_dirs,
    }

    if request.headers.get("HX-Request"):
        return render(request, "partials/devices_table.html", context)

    return render(request, "devices/device_list.html", context)


# ------------------------------
# Device Detail / Stats
# ------------------------------

@login_required
def device_detail(request, deviceid):
    device = _accessible_device_or_404(request.user, deviceid)

    # ---------------------------
    # PERIOD FILTER
    # ---------------------------
    period = request.GET.get("period", "all")
    now_time = timezone.now()

    period_map = {
        "1d": timedelta(hours=24),
        "3d": timedelta(days=3),
        "7d": timedelta(days=7),
        "14d": timedelta(days=14),
        "30d": timedelta(days=30),
        "60d": timedelta(days=60),
        "90d": timedelta(days=90),
        "180d": timedelta(days=180),
        "365d": timedelta(days=365),
    }

    duration = period_map.get(period)

    start_time = now_time - duration if duration else None
    previous_start = start_time - duration if duration else None
    previous_end = start_time if duration else None

    # ---------------------------
    # READINGS CURRENT PERIOD
    # ---------------------------
    readings_qs = DeviceData.objects.filter(deviceid=deviceid)

    if start_time:
        readings_qs = readings_qs.filter(time__gte=start_time)

    readings = readings_qs.order_by("time")

    last_seen = (
        timezone.localtime(readings.last().time)
        if readings.exists()
        else None
    )

    # ---------------------------
    # READINGS PREVIOUS PERIOD
    # ---------------------------
    previous_readings = DeviceData.objects.none()

    if duration:
        previous_readings = DeviceData.objects.filter(
            deviceid=deviceid,
            time__gte=previous_start,
            time__lt=previous_end
        )

    # ---------------------------
    # COOKING EVENT DETECTION
    # ---------------------------
    cooking_events = []
    current_event = []
    prev_time = None

    for r in readings:
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
    # PREVIOUS COOKING EVENTS
    # ---------------------------
    previous_events = []
    current_event = []
    prev_time = None

    for r in previous_readings.order_by("time"):
        if prev_time:
            gap = (r.time - prev_time).total_seconds()

            if gap > COOKING_GAP_SECONDS:
                if current_event:
                    previous_events.append(current_event)
                current_event = []

        current_event.append(r)
        prev_time = r.time

    if current_event:
        previous_events.append(current_event)

    # ---------------------------
    # COOKING METRICS
    # ---------------------------
    cooking_event_rows = []
    total_cooking_time_minutes = 0

    for idx, event in enumerate(cooking_events, start=1):
        start = timezone.localtime(event[0].time)
        end = timezone.localtime(event[-1].time)

        duration_minutes = (end - start).total_seconds() / 60
        energy_kwh = sum(float(r.kwh or 0) for r in event)

        total_cooking_time_minutes += duration_minutes

        cooking_event_rows.append({
            "index": idx,
            "start": start,
            "end": end,
            "duration": round(duration_minutes, 1),
            "energy": round(energy_kwh, 3),
        })

    cooking_events_count = len(cooking_events)
    previous_cooking_events = len(previous_events)

    # ---------------------------
    # SORTING
    # ---------------------------
    sort = request.GET.get("sort", "start")
    direction = request.GET.get("dir", "desc")

    allowed_sorts = {
        "start": "start",
        "end": "end",
        "duration": "duration",
        "energy": "energy",
    }

    reverse = direction == "desc"

    cooking_event_rows.sort(
        key=lambda x: x[allowed_sorts.get(sort, "start")],
        reverse=reverse
    )

    next_dirs = {}
    for key in allowed_sorts:
        next_dirs[key] = "desc" if (key == sort and direction == "asc") else "asc"

    # ---------------------------
    # PAGINATION
    # ---------------------------
    allowed_page_sizes = [10, 25, 50, 100]
    try:
        page_size = int(request.GET.get("page_size", 10))
    except (TypeError, ValueError):
        page_size = 10
    if page_size not in allowed_page_sizes:
        page_size = 10

    paginator = Paginator(cooking_event_rows, page_size)
    page_number = request.GET.get("page")
    cooking_event_rows_paginated = paginator.get_page(page_number)

    # ---------------------------
    # ENERGY METRICS
    # ---------------------------
    total_kwh = readings.aggregate(total=Sum("kwh"))["total"] or 0
    previous_kwh = previous_readings.aggregate(total=Sum("kwh"))["total"] or 0

    ENERGY_PRICE = 14.32
    CO2_PER_KWH = 0.41

    energy_cost = total_kwh * ENERGY_PRICE
    previous_cost = previous_kwh * ENERGY_PRICE

    co2_emissions = total_kwh * CO2_PER_KWH
    previous_co2 = previous_kwh * CO2_PER_KWH

    # ---------------------------
    # COOKING TIME
    # ---------------------------
    previous_cooking_time = 0

    for event in previous_events:
        start = event[0].time
        end = event[-1].time
        previous_cooking_time += (end - start).total_seconds() / 60

    # ---------------------------
    # PERCENTAGE CHANGE
    # ---------------------------
    def percent_change(current, previous):
        if previous == 0:
            return 0

        return round(((current - previous) / previous) * 100, 2)

    kwh_change = percent_change(total_kwh, previous_kwh)
    co2_change = percent_change(co2_emissions, previous_co2)
    events_change = percent_change(cooking_events_count, previous_cooking_events)
    cooking_time_change = percent_change(total_cooking_time_minutes, previous_cooking_time)
    cost_change = percent_change(energy_cost, previous_cost)

    # ---------------------------
    # DAILY ENERGY CHART
    # ---------------------------
    daily_energy = {}

    for r in readings:
        day = timezone.localtime(r.time).date()
        daily_energy[day] = daily_energy.get(day, 0) + float(r.kwh or 0)

    sorted_days = sorted(daily_energy.keys())

    energy_labels = [d.strftime("%d %b") for d in sorted_days]
    energy_data = [round(daily_energy[d], 3) for d in sorted_days]

    # ---------------------------
    # COOKING EVENTS CHART
    # ---------------------------
    daily_events = {}

    for event in cooking_events:
        day = timezone.localtime(event[0].time).date()
        daily_events[day] = daily_events.get(day, 0) + 1

    cooking_event_labels = energy_labels
    cooking_event_data = [daily_events.get(d, 0) for d in sorted_days]

    # ---------------------------
    # HTMX TABLE
    # ---------------------------
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "partials/cooking_events_table.html",
            {
                "cooking_event_rows": cooking_event_rows_paginated,
                "page_size": page_size,
                "page_size_options": allowed_page_sizes,
                "current_sort": sort,
                "current_dir": direction,
                "next_dirs": next_dirs,
                "device": device,
                "period": period,
            },
        )

    context = {
        "device": device,
        "period": period,
        "last_seen": last_seen,

        "total_kwh": round(total_kwh, 3),
        "cooking_events": cooking_events_count,
        "cooking_time": round(total_cooking_time_minutes, 1),
        "energy_cost": round(energy_cost, 2),
        "co2_emissions": round(co2_emissions, 2),

        "kwh_change": kwh_change,
        "co2_change": co2_change,
        "events_change": events_change,
        "cooking_time_change": cooking_time_change,
        "cost_change": cost_change,

        "energy_labels": energy_labels,
        "energy_data": energy_data,
        "cooking_event_labels": cooking_event_labels,
        "cooking_event_data": cooking_event_data,

        "cooking_event_rows": cooking_event_rows_paginated,
        "page_size": page_size,
        "page_size_options": allowed_page_sizes,

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
        current_status = request.POST.get("active", "false").lower() == "true"

        api_payload = {
            "selectedDev": deviceid,
            "status": current_status
        }

        response = requests.post(
            "https://appliapay.com/changeStatus",
            json=api_payload,
            timeout=10
        )

        if response.status_code != 200:
            return HttpResponse("External API error", status=502)

        data = response.json()

        new_status = data.get("status", not current_status)

        if isinstance(new_status, str):
            new_status = new_status.lower() == "true"

        updated_time_str = data.get("time")
        updated_time = None

        if new_status:
            notify(
                request.user,
                "Device Activation",
                f"{deviceid} has been activated.",
                "success"
            )
        else:
            notify(
                request.user,
                "Device Deactivation",
                f"{deviceid} has been deactivated.",
                "warning"
            )

        if updated_time_str:
            dt = parse_datetime(updated_time_str)
            if dt:
                updated_time = make_aware(dt) if is_naive(dt) else dt

        start_of_day = now().replace(hour=0, minute=0, second=0, microsecond=0)

        device = _accessible_device_or_404(request.user, deviceid)
        device.active = new_status
        device.save(update_fields=["active"])

        kwh_today = kwh_for_device(device, start_of_day, now())

        return render(
            request,
            "partials/device-row.html",
            {
                "device": device,
                "deviceid": device.deviceid,
                "active": device.active,
                "last_seen": last_energy_timestamp(device),
                "kwh_today": kwh_today,
                "user": request.user,
                "organization": device.organization,
                "organizations": device.organizations.all(),
                "is_superuser": _user_is_device_admin(request.user),
                "is_admin": _user_is_device_admin(request.user),
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
        current_status = request.POST.get("active", "false").lower() == "true"

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

        new_status = data.get("status", not current_status)

        if isinstance(new_status, str):
            new_status = new_status.lower() == "true"

        updated_time_str = data.get("time")
        updated_time = None

        if updated_time_str:
            dt = parse_datetime(updated_time_str)
            if dt:
                updated_time = make_aware(dt) if is_naive(dt) else dt

        device = _accessible_device_or_404(request.user, deviceid)
        device.active = new_status
        device.save(update_fields=["active"])

        return render(
            request,
            "partials/device_status_partial.html",
            {
                "device": device,
                "last_seen": last_energy_timestamp(device)
            }
        )

    except requests.exceptions.RequestException as e:
        return HttpResponse(f"API request failed: {e}", status=500)

    except Exception as e:
        return HttpResponse(f"Unexpected error: {e}", status=500)


def superuser_required(view):
    return user_passes_test(lambda u: u.is_superuser)(view)


@superuser_required
def device_create(request):
    form = DeviceForm(request.POST or None, user=request.user)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            device = form.save()

            if form.cleaned_data.get("add_to_inventory"):
                InventoryItem.objects.get_or_create(
                    serial_number=device.deviceid,
                    defaults={
                        "name": form.cleaned_data["inventory_name"],
                        "product_type": form.cleaned_data["product_type"],
                        "current_warehouse": form.cleaned_data["warehouse"],
                    }
                )

        return redirect("devices:device_list")

    return render(request, "devices/device_form.html", {
        "form": form,
        "title": "Add Device"
    })


@superuser_required
def device_edit(request, deviceid):
    device = get_object_or_404(DeviceInfo, deviceid=deviceid)

    inventory = InventoryItem.objects.filter(
        serial_number=device.deviceid
    ).first()

    form = DeviceForm(request.POST or None, instance=device, user=request.user)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            old_deviceid = device.deviceid

            device = form.save()

            new_deviceid = device.deviceid

            if old_deviceid != new_deviceid:
                TrackKwh.objects.filter(deviceid=old_deviceid).update(
                    deviceid=new_deviceid
                )

                InventoryItem.objects.filter(
                    serial_number=old_deviceid
                ).update(
                    serial_number=new_deviceid
                )

            add_to_inventory = form.cleaned_data.get("add_to_inventory")

            if add_to_inventory:
                InventoryItem.objects.update_or_create(
                    serial_number=device.deviceid,
                    defaults={
                        "name": form.cleaned_data["inventory_name"],
                        "product_type": form.cleaned_data["product_type"],
                        "current_warehouse": form.cleaned_data["warehouse"],
                    }
                )
            else:
                InventoryItem.objects.filter(
                    serial_number=device.deviceid
                ).delete()

        return redirect("devices:device_list")

    if request.method == "GET" and inventory:
        form.initial.update({
            "add_to_inventory": True,
            "inventory_name": inventory.name,
            "product_type": inventory.product_type,
            "warehouse": inventory.current_warehouse,
        })

    return render(request, "devices/device_form.html", {
        "form": form,
        "title": "Edit Device"
    })


@superuser_required
@require_POST
def device_delete(request, deviceid):
    device = get_object_or_404(DeviceInfo, deviceid=deviceid)

    with transaction.atomic():
        InventoryItem.objects.filter(
            serial_number=device.deviceid
        ).delete()

        TrackKwh.objects.filter(
            deviceid=device.deviceid
        ).delete()

        device.delete()

    return redirect("devices:device_list")


@superuser_required
def device_bulk_create(request):
    form = BulkDeviceCreateForm(request.POST or None, user=request.user)

    if request.method == "POST" and form.is_valid():
        deviceids = form.cleaned_data["deviceids"]
        organizations = form.cleaned_data["organizations"]
        primary_organization = organizations.first()
        active = form.cleaned_data["active"]

        if not primary_organization:
            messages.error(request, "Select at least one organization.")
            return redirect("devices:device_bulk_create")

        existing_ids = set(
            DeviceInfo.objects.filter(deviceid__in=deviceids)
            .values_list("deviceid", flat=True)
        )

        created_count = 0
        skipped = []

        with transaction.atomic():
            for deviceid in deviceids:
                if deviceid in existing_ids:
                    skipped.append(deviceid)
                    continue

                device = DeviceInfo.objects.create(
                    deviceid=deviceid,
                    active=active,
                    organization=primary_organization,
                )

                device.organizations.set(organizations)
                created_count += 1

                # --- ADD INVENTORY ITEM IF SELECTED ---
                if form.cleaned_data.get("add_to_inventory"):
                    InventoryItem.objects.get_or_create(
                        serial_number=device.deviceid,
                        defaults={
                            "name": form.cleaned_data["inventory_name"] or device.deviceid,
                            "product_type": form.cleaned_data["product_type"] or "Hardware",
                            "current_warehouse": form.cleaned_data["warehouse"] or None,
                        }
                    )

        if created_count:
            messages.success(request, f"{created_count} device(s) added successfully.")

        if skipped:
            messages.warning(
                request,
                f"Skipped {len(skipped)} duplicate device(s): {', '.join(skipped[:10])}"
                + ("..." if len(skipped) > 10 else "")
            )

        return redirect("devices:device_list")

    return render(request, "devices/device_bulk_form.html", {
        "form": form,
        "title": "Bulk Add Devices",
    })


@login_required
@require_POST
def device_bulk_action(request):
    action = request.POST.get("bulk_action")
    selected_ids = request.POST.getlist("selected_devices")
    target_org_id = request.POST.get("target_org")

    if not selected_ids:
        messages.warning(request, "Select at least one device first.")
        return redirect("devices:device_list")

    devices, _, _ = _accessible_device_queryset(request.user)
    devices = devices.filter(deviceid__in=selected_ids).distinct()

    if not devices.exists():
        messages.error(request, "No accessible devices matched your selection.")
        return redirect("devices:device_list")

    # ----------------------------------------------------
    # ADD SELECTED DEVICES TO ANOTHER ORGANIZATION
    # ----------------------------------------------------
    if action == "add_to_org":
        if not _user_is_device_admin(request.user):
            messages.error(
                request,
                "You do not have permission to assign devices to organizations."
            )
            return redirect("devices:device_list")

        if not target_org_id:
            messages.warning(
                request,
                "Choose an organization to assign the selected devices to."
            )
            return redirect("devices:device_list")

        target_org = get_object_or_404(Organization, id=target_org_id)

        updated_count = 0
        already_assigned_count = 0

        with transaction.atomic():
            for device in devices:
                if device.organizations.filter(id=target_org.id).exists():
                    already_assigned_count += 1
                    continue

                device.organizations.add(target_org)

                if not device.organization_id:
                    device.organization = target_org
                    device.save(update_fields=["organization"])

                updated_count += 1

        if updated_count:
            messages.success(
                request,
                f"{updated_count} device(s) added to {target_org.name}."
            )

        if already_assigned_count:
            messages.info(
                request,
                f"{already_assigned_count} device(s) were already assigned to {target_org.name}."
            )

        return redirect("devices:device_list")

    # ----------------------------------------------------
    # ACTIVATE / DEACTIVATE SELECTED DEVICES
    # ----------------------------------------------------
    if action in ["activate", "deactivate"]:
        target_status = action == "activate"

        success_count = 0
        failed = []

        for device in devices:
            try:
                response = requests.post(
                    "https://appliapay.com/changeStatus",
                    json={
                        "selectedDev": device.deviceid,
                        "status": target_status,
                    },
                    timeout=10
                )

                if response.status_code != 200:
                    failed.append(device.deviceid)
                    continue

                data = response.json()
                api_status = data.get("status", target_status)

                if isinstance(api_status, str):
                    api_status = api_status.lower() == "true"

                device.active = api_status
                device.save(update_fields=["active"])

                success_count += 1

            except requests.exceptions.RequestException:
                failed.append(device.deviceid)

        if success_count:
            action_label = "activated" if target_status else "deactivated"

            messages.success(
                request,
                f"{success_count} device(s) {action_label} successfully."
            )

            notify(
                request.user,
                "Bulk Device Update",
                f"{success_count} device(s) {action_label}.",
                "success" if target_status else "warning"
            )

        if failed:
            messages.warning(
                request,
                f"{len(failed)} device(s) could not be updated through the external API: "
                f"{', '.join(failed[:10])}" + ("..." if len(failed) > 10 else "")
            )

        return redirect("devices:device_list")

    # ----------------------------------------------------
    # DELETE SELECTED DEVICES
    # ----------------------------------------------------
    if action == "delete":
        if not _user_is_device_admin(request.user):
            messages.error(
                request,
                "You do not have permission to delete devices in bulk."
            )
            return redirect("devices:device_list")

        deleted_count = devices.count()
        deviceids = list(devices.values_list("deviceid", flat=True))

        with transaction.atomic():
            InventoryItem.objects.filter(serial_number__in=deviceids).delete()
            TrackKwh.objects.filter(deviceid__in=deviceids).delete()
            devices.delete()

        messages.success(request, f"{deleted_count} device(s) deleted successfully.")
        return redirect("devices:device_list")

    messages.error(request, "Choose a valid bulk action.")
    return redirect("devices:device_list")


@login_required
def device_live_view(request, deviceid):
    device = _accessible_device_or_404(request.user, deviceid)

    return render(request, "devices/device_live.html", {
        "device": device
    })


# ------------------------------
# Device Schedules
# ------------------------------

class DeviceScheduleListView(ListView):
    model = DeviceCommandSchedule
    template_name = "devices/device_schedule_list.html"
    context_object_name = "schedules"
    ordering = ["-scheduled_time"]

    page_size_options = [10, 25, 50, 100]

    def get_queryset(self):
        user = self.request.user

        qs = (
            DeviceCommandSchedule.objects
            .select_related("created_by", "organization")
            .prefetch_related("devices")
            .order_by("-scheduled_time")
        )

        if _user_is_device_admin(user):
            return qs

        accessible_orgs = get_accessible_organizations(user)

        return qs.filter(organization__in=accessible_orgs)

    def get_paginate_by(self, queryset):
        try:
            page_size = int(self.request.GET.get("page_size", 10))
        except (TypeError, ValueError):
            page_size = 10

        if page_size not in self.page_size_options:
            page_size = 10

        self.page_size = page_size
        return page_size

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_size"] = getattr(self, "page_size", 10)
        context["page_size_options"] = self.page_size_options
        context["total_results"] = self.get_queryset().count()
        return context


class DeviceScheduleCreateView(CreateView):
    model = DeviceCommandSchedule
    form_class = DeviceCommandScheduleForm
    template_name = "devices/device_schedule_form.html"
    success_url = reverse_lazy("devices:device_schedule_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_schedule_organization(self, form):
        user = self.request.user

        if not _user_is_device_admin(user):
            return user.organization

        selected_devices = form.cleaned_data.get("devices")

        if selected_devices:
            first_device = (
                selected_devices
                .select_related("organization")
                .first()
            )

            if first_device and first_device.organization_id:
                return first_device.organization

        if getattr(user, "organization_id", None):
            return user.organization

        return None

    def form_valid(self, form):
        organization = self.get_schedule_organization(form)

        if organization is None:
            form.add_error(
                None,
                "Could not determine the organization for this schedule. "
                "Please select devices that belong to an organization.",
            )
            return self.form_invalid(form)

        form.instance.created_by = self.request.user
        form.instance.organization = organization

        return super().form_valid(form)


class DeviceScheduleUpdateView(UpdateView):
    model = DeviceCommandSchedule
    form_class = DeviceCommandScheduleForm
    template_name = "devices/device_schedule_form.html"
    success_url = reverse_lazy("devices:device_schedule_list")

    def get_queryset(self):
        user = self.request.user

        if _user_is_device_admin(user):
            return DeviceCommandSchedule.objects.all()

        accessible_orgs = get_accessible_organizations(user)

        return DeviceCommandSchedule.objects.filter(
            organization__in=accessible_orgs
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_schedule_organization(self, form):
        user = self.request.user

        if not _user_is_device_admin(user):
            return user.organization

        selected_devices = form.cleaned_data.get("devices")

        if selected_devices:
            first_device = (
                selected_devices
                .select_related("organization")
                .first()
            )

            if first_device and first_device.organization_id:
                return first_device.organization

        if self.object and self.object.organization_id:
            return self.object.organization

        if getattr(user, "organization_id", None):
            return user.organization

        return None

    def form_valid(self, form):
        organization = self.get_schedule_organization(form)

        if organization is None:
            form.add_error(
                None,
                "Could not determine the organization for this schedule. "
                "Please select devices that belong to an organization.",
            )
            return self.form_invalid(form)

        form.instance.organization = organization

        return super().form_valid(form)


class DeviceScheduleDeleteView(DeleteView):
    model = DeviceCommandSchedule
    template_name = "devices/device_schedule_confirm_delete.html"
    success_url = reverse_lazy("devices:device_schedule_list")

    def get_queryset(self):
        user = self.request.user

        if _user_is_device_admin(user):
            return DeviceCommandSchedule.objects.all()

        accessible_orgs = get_accessible_organizations(user)

        return DeviceCommandSchedule.objects.filter(
            organization__in=accessible_orgs
        )


def trigger_schedule(request, pk):
    user = request.user

    if _user_is_device_admin(user):
        schedule = get_object_or_404(DeviceCommandSchedule, pk=pk)
    else:
        accessible_orgs = get_accessible_organizations(user)

        schedule = get_object_or_404(
            DeviceCommandSchedule,
            pk=pk,
            organization__in=accessible_orgs
        )

    if schedule.executed:
        messages.warning(request, "Schedule already executed!")
        return redirect("devices:device_schedule_list")

    for device in schedule.devices.all():
        result = call_change_status_api(device.deviceid, schedule.action)

        if result["success"]:
            messages.success(request, f"{schedule.action} sent to {device}")
        else:
            messages.error(request, f"Error for {device}: {result['error']}")

    schedule.executed = True
    schedule.save()

    return redirect("devices:device_schedule_list")