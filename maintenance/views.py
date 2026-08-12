from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from notifications.utils import notify
from organizations.models import Organization

from .forms import (
    MaintenanceCommentForm,
    MaintenancePhotoForm,
    MaintenanceRecordForm,
    MaintenanceStatusForm,
)
from .models import MaintenanceRecord
from .services import (
    MAINTENANCE_WAREHOUSE_ID,
    MaintenanceWarehouseMissing,
    close_record,
    get_user_maintenance_records,
    is_superadmin,
    log_status_change,
    open_record_for_item,
    send_item_to_maintenance,
)

PERIOD_DAYS = {
    "1d": 1,
    "3d": 3,
    "7d": 7,
    "14d": 14,
    "30d": 30,
    "60d": 60,
    "90d": 90,
    "180d": 180,
    "365d": 365,
}


def _superadmin_required(user):
    return is_superadmin(user)


def _get_record_for_user_or_404(request, pk):
    return get_object_or_404(get_user_maintenance_records(request.user), pk=pk)


def _public_url(request, record):
    return request.build_absolute_uri(
        reverse("maintenance:maintenance_public", args=[record.token])
    )


@login_required
def maintenance_list(request):
    user = request.user
    user_is_superadmin = is_superadmin(user)

    records = get_user_maintenance_records(user)

    search_query = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()
    priority_filter = (request.GET.get("priority") or "").strip()
    org_filter = (request.GET.get("org") or "").strip()
    period = (request.GET.get("period") or "all").strip()
    page_size = request.GET.get("page_size") or "25"

    if search_query:
        records = records.filter(
            Q(serial_number__icontains=search_query)
            | Q(item_name__icontains=search_query)
            | Q(product_type__icontains=search_query)
            | Q(reported_fault__icontains=search_query)
        )

    if status_filter == "open":
        records = records.filter(status__in=MaintenanceRecord.OPEN_STATUSES)
    elif status_filter == "closed":
        records = records.filter(status__in=MaintenanceRecord.CLOSED_STATUSES)
    elif status_filter:
        records = records.filter(status=status_filter)

    if priority_filter:
        records = records.filter(priority=priority_filter)

    if user_is_superadmin and org_filter:
        records = records.filter(
            Q(organization_id=org_filter)
            | Q(source_warehouse__organization_id=org_filter)
            | Q(item__current_warehouse__organization_id=org_filter)
        )

    if period in PERIOD_DAYS:
        records = records.filter(
            created_at__gte=timezone.now() - timedelta(days=PERIOD_DAYS[period])
        )

    open_count = records.filter(status__in=MaintenanceRecord.OPEN_STATUSES).count()
    fixed_count = records.filter(status=MaintenanceRecord.STATUS_FIXED).count()
    in_progress_count = records.filter(status=MaintenanceRecord.STATUS_IN_PROGRESS).count()
    total_count = records.count()

    try:
        page_size_int = max(5, min(int(page_size), 200))
    except (TypeError, ValueError):
        page_size_int = 25

    paginator = Paginator(records, page_size_int)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "maintenance/maintenance_list.html",
        {
            "page_obj": page_obj,
            "records": page_obj.object_list,
            "total_count": total_count,
            "open_count": open_count,
            "in_progress_count": in_progress_count,
            "fixed_count": fixed_count,
            "search_query": search_query,
            "status_filter": status_filter,
            "priority_filter": priority_filter,
            "org_filter": org_filter,
            "period": period,
            "page_size": page_size_int,
            "is_superadmin": user_is_superadmin,
            "organizations": Organization.objects.order_by("name") if user_is_superadmin else [],
            "status_choices": MaintenanceRecord.STATUS_CHOICES,
            "priority_choices": MaintenanceRecord.PRIORITY_CHOICES,
        },
    )


@login_required
def maintenance_create(request):
    if not _superadmin_required(request.user):
        return HttpResponseForbidden("Only superadmins can create maintenance records.")

    if request.method == "POST":
        form = MaintenanceRecordForm(request.POST)

        if form.is_valid():
            item = form.cleaned_data["item"]

            existing = open_record_for_item(item)

            if existing:
                form.add_error(
                    "item",
                    f"{item.serial_number} already has an open maintenance record ({existing.reference}).",
                )
            else:
                try:
                    with transaction.atomic():
                        record = send_item_to_maintenance(
                            item=item,
                            user=request.user,
                            reported_fault=form.cleaned_data.get("reported_fault"),
                            priority=form.cleaned_data.get("priority"),
                        )

                    notify(
                        request.user,
                        "Maintenance Record Created",
                        (
                            f"{record.serial_number} ({record.item_name}) was moved to "
                            f"maintenance as {record.reference}."
                        ),
                        "info",
                    )

                    return redirect("maintenance:maintenance_detail", pk=record.pk)

                except MaintenanceWarehouseMissing as exc:
                    form.add_error(None, str(exc))

                except ValueError as exc:
                    form.add_error(None, str(exc))
    else:
        form = MaintenanceRecordForm()

    return render(
        request,
        "maintenance/maintenance_form.html",
        {
            "form": form,
            "maintenance_warehouse_id": MAINTENANCE_WAREHOUSE_ID,
        },
    )


@login_required
def maintenance_detail(request, pk):
    record = _get_record_for_user_or_404(request, pk)
    user_is_superadmin = is_superadmin(request.user)

    return render(
        request,
        "maintenance/maintenance_detail.html",
        {
            "record": record,
            "status_updates": record.status_updates.select_related("changed_by"),
            "comments": (
                record.comments.select_related("author")
                if user_is_superadmin
                else record.comments.filter(is_public=True).select_related("author")
            ),
            "photos": (
                record.photos.all()
                if user_is_superadmin
                else record.photos.filter(is_public=True)
            ),
            "status_form": MaintenanceStatusForm(initial={"status": record.status}),
            "comment_form": MaintenanceCommentForm(),
            "photo_form": MaintenancePhotoForm(),
            "public_url": _public_url(request, record),
            "is_superadmin": user_is_superadmin,
        },
    )


@login_required
def maintenance_status_update(request, pk):
    if not _superadmin_required(request.user):
        return HttpResponseForbidden("Only superadmins can update maintenance records.")

    record = get_object_or_404(MaintenanceRecord, pk=pk)

    if request.method != "POST":
        return redirect("maintenance:maintenance_detail", pk=record.pk)

    form = MaintenanceStatusForm(request.POST)

    if not form.is_valid():
        messages.error(request, "Could not update the maintenance status.")
        return redirect("maintenance:maintenance_detail", pk=record.pk)

    status = form.cleaned_data["status"]
    note = form.cleaned_data.get("note")
    return_warehouse = form.cleaned_data.get("return_warehouse")

    try:
        with transaction.atomic():
            if status in MaintenanceRecord.CLOSED_STATUSES:
                close_record(
                    record,
                    status=status,
                    user=request.user,
                    note=note,
                    return_warehouse=return_warehouse,
                )
            else:
                record.status = status
                record.closed_at = None
                record.save(update_fields=["status", "closed_at", "updated_at"])
                log_status_change(record, status, note, request.user)

        messages.success(request, f"{record.reference} updated to {record.get_status_display()}.")

    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("maintenance:maintenance_detail", pk=record.pk)


@login_required
def maintenance_comment_add(request, pk):
    if not _superadmin_required(request.user):
        return HttpResponseForbidden("Only superadmins can comment on maintenance records.")

    record = get_object_or_404(MaintenanceRecord, pk=pk)

    if request.method == "POST":
        form = MaintenanceCommentForm(request.POST)

        if form.is_valid():
            comment = form.save(commit=False)
            comment.record = record
            comment.author = request.user
            comment.save()
            messages.success(request, "Comment added.")
        else:
            messages.error(request, "Could not add the comment.")

    return redirect("maintenance:maintenance_detail", pk=record.pk)


@login_required
def maintenance_photo_add(request, pk):
    if not _superadmin_required(request.user):
        return HttpResponseForbidden("Only superadmins can upload maintenance photos.")

    record = get_object_or_404(MaintenanceRecord, pk=pk)

    if request.method == "POST":
        form = MaintenancePhotoForm(request.POST, request.FILES)

        if form.is_valid():
            photo = form.save(commit=False)
            photo.record = record
            photo.uploaded_by = request.user
            photo.save()
            messages.success(request, "Photo uploaded.")
        else:
            messages.error(request, "Could not upload the photo.")

    return redirect("maintenance:maintenance_detail", pk=record.pk)


def maintenance_public(request, token):
    try:
        record = (
            MaintenanceRecord.objects
            .select_related("item", "item__current_warehouse", "source_warehouse")
            .get(token=token)
        )
    except MaintenanceRecord.DoesNotExist:
        raise Http404("Maintenance record not found.")

    return render(
        request,
        "maintenance/maintenance_public.html",
        {
            "record": record,
            "status_updates": record.status_updates.all(),
            "comments": record.comments.filter(is_public=True),
            "photos": record.photos.filter(is_public=True),
        },
    )
