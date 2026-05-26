from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from devices.models import DeviceInfo
from inventory.models import InventoryItem, InventoryMovement
from notifications.utils import notify

from .models import DeviceOrder
from .forms import DeviceOrderForm, DeviceOrderRejectForm, DeviceOrderFulfillForm


def can_manage_orders(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or getattr(user, "role", None) in ["superadmin", "admin"]
        )
    )


def user_has_global_order_access(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) == "superadmin")
    )


def accessible_order_queryset(user):
    qs = DeviceOrder.objects.select_related(
        "requested_by",
        "organization",
        "warehouse",
        "approved_by",
        "fulfilled_by",
    )

    if user_has_global_order_access(user):
        return qs

    return qs.filter(organization=user.organization)


@login_required
def order_list(request):
    user = request.user

    orders = accessible_order_queryset(user)

    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    page_size = request.GET.get("page_size", "10")

    if q:
        orders = orders.filter(
            Q(product_type__icontains=q) |
            Q(notes__icontains=q) |
            Q(requested_by__email__icontains=q)
        )

    if status:
        orders = orders.filter(status=status)

    try:
        page_size = int(page_size)
    except ValueError:
        page_size = 10

    if page_size not in [10, 25, 50, 100]:
        page_size = 10

    paginator = Paginator(orders, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    template = "partials/device_orders_table.html" if request.headers.get("HX-Request") == "true" else "device_orders/order_list.html"

    return render(request, template, {
        "orders": page_obj,
        "page_obj": page_obj,
        "q": q,
        "status": status,
        "page_size": page_size,
        "page_size_options": [10, 25, 50, 100],
        "can_manage": can_manage_orders(user),
        "status_choices": DeviceOrder.STATUS_CHOICES,
    })


@login_required
def order_create(request):
    if request.method == "POST":
        form = DeviceOrderForm(request.POST, user=request.user)
        if form.is_valid():
            order = form.save(commit=False)
            order.requested_by = request.user
            order.organization = request.user.organization
            order.status = "submitted"
            order.save()

            notify(
                request.user,
                "Device Order Submitted",
                f"Your order for {order.quantity} {order.product_type}(s) has been submitted.",
                "success",
            )
            return redirect("device_orders:order_detail", pk=order.pk)
    else:
        form = DeviceOrderForm(user=request.user)

    return render(request, "device_orders/order_form.html", {
        "form": form,
        "title": "New Device Order",
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(accessible_order_queryset(request.user), pk=pk)

    return render(request, "device_orders/order_detail.html", {
        "order": order,
        "can_manage": can_manage_orders(request.user),
    })


@login_required
def order_approve(request, pk):
    if not can_manage_orders(request.user):
        return redirect("device_orders:order_list")

    order = get_object_or_404(accessible_order_queryset(request.user), pk=pk)

    if order.status == "submitted":
        order.status = "approved"
        order.approved_by = request.user
        order.approved_at = timezone.now()
        order.save()

        notify(
            request.user,
            "Device Order Approved",
            f"Order #{order.id} has been approved.",
            "success",
        )

    return redirect("device_orders:order_detail", pk=order.pk)


@login_required
def order_reject(request, pk):
    if not can_manage_orders(request.user):
        return redirect("device_orders:order_list")

    order = get_object_or_404(accessible_order_queryset(request.user), pk=pk)

    if request.method == "POST":
        form = DeviceOrderRejectForm(request.POST)
        if form.is_valid() and order.status == "submitted":
            order.status = "rejected"
            order.rejection_reason = form.cleaned_data["rejection_reason"]
            order.save()

            notify(
                request.user,
                "Device Order Rejected",
                f"Order #{order.id} has been rejected.",
                "warning",
            )
            return redirect("device_orders:order_detail", pk=order.pk)
    else:
        form = DeviceOrderRejectForm()

    return render(request, "device_orders/order_reject.html", {
        "form": form,
        "order": order,
    })


@login_required
def order_cancel(request, pk):
    order = get_object_or_404(accessible_order_queryset(request.user), pk=pk)

    if order.requested_by != request.user and not can_manage_orders(request.user):
        return redirect("device_orders:order_list")

    if order.status == "submitted":
        order.status = "cancelled"
        order.save()

        notify(
            request.user,
            "Device Order Cancelled",
            f"Order #{order.id} has been cancelled.",
            "warning",
        )

    return redirect("device_orders:order_detail", pk=order.pk)


@login_required
def order_fulfill(request, pk):
    if not can_manage_orders(request.user):
        return redirect("device_orders:order_list")

    order = get_object_or_404(accessible_order_queryset(request.user), pk=pk)

    if order.status != "approved":
        return redirect("device_orders:order_detail", pk=order.pk)

    if request.method == "POST":
        form = DeviceOrderFulfillForm(request.POST, order=order)
        if form.is_valid():
            device_ids = form.cleaned_data["device_ids"]

            existing = DeviceInfo.objects.filter(deviceid__in=device_ids).values_list("deviceid", flat=True)
            if existing:
                form.add_error("device_ids", f"These devices already exist: {', '.join(existing)}")
            else:
                with transaction.atomic():
                    created_devices = []

                    for deviceid in device_ids:
                        device = DeviceInfo.objects.create(
                            deviceid=deviceid,
                            active=True,
                            organization=order.organization,
                        )
                        device.organizations.set([order.organization])
                        created_devices.append(device)

                        item = InventoryItem.objects.create(
                            name=order.product_type,
                            serial_number=deviceid,
                            product_type=order.product_type,
                            item_type=InventoryItem.TYPE_UNIQUE,
                            quantity=1,
                            current_warehouse=order.warehouse,
                        )

                        InventoryMovement.objects.create(
                            item=item,
                            to_warehouse=order.warehouse,
                            moved_by=request.user,
                            note=f"Created from device order #{order.id}",
                        )

                    order.status = "fulfilled"
                    order.fulfilled_by = request.user
                    order.fulfilled_at = timezone.now()
                    order.save()

                notify(
                    request.user,
                    "Device Order Fulfilled",
                    f"Order #{order.id} has been fulfilled with {len(created_devices)} device(s).",
                    "success",
                )
                return redirect("device_orders:order_detail", pk=order.pk)
    else:
        form = DeviceOrderFulfillForm(order=order)

    return render(request, "device_orders/order_fulfill.html", {
        "form": form,
        "order": order,
    })