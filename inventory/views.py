from collections import defaultdict
from datetime import timedelta
from io import BytesIO
import os
from django.db import transaction, IntegrityError, router

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from xhtml2pdf import pisa
from django.core.paginator import Paginator
from .models import (
    InventoryItem,
    Warehouse,
    InventoryMovement,
    InventoryDeliveryNote,
    InventoryDeliveryNoteItem,
)
from .forms import (
    WarehouseForm,
    InventoryItemForm,
    BulkInventoryItemForm,
    InventoryMoveForm,
    BulkInventoryMoveForm,
    DeliveryNoteReceiveForm,
)
from notifications.utils import notify
from organizations.models import Organization


# =========================
# HELPERS
# =========================

def is_superadmin(user):
    return user.is_superuser or getattr(user, "role", None) == "superadmin"


def get_allowed_warehouses(user):
    if is_superadmin(user):
        return Warehouse.objects.all()

    return Warehouse.objects.filter(organization=user.organization)


def get_allowed_inventory_items(user):
    qs = InventoryItem.objects.select_related("current_warehouse")

    if is_superadmin(user):
        return qs

    return qs.filter(current_warehouse__organization=user.organization)


def format_duration(delta):
    total_seconds = max(int(delta.total_seconds()), 0)

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    if days == 1:
        return "1 day"

    if days > 1:
        return f"{days} days"

    if hours == 1:
        return "1 hour"

    if hours > 1:
        return f"{hours} hours"

    if minutes <= 1:
        return "Less than 1 minute"

    return f"{minutes} minutes"


def build_timeline_movements(movements_qs):
    """
    Calculates how long the item/quantity stayed in each destination warehouse.

    Movement A moves stock to Warehouse 1.
    Movement B happens 5 days later.
    Movement A shows 5 days spent in Warehouse 1.

    The latest movement shows time from that movement until now.
    """
    now = timezone.now()
    movements_asc = list(movements_qs.order_by("date_moved"))

    for index, movement in enumerate(movements_asc):
        next_movement = (
            movements_asc[index + 1]
            if index + 1 < len(movements_asc)
            else None
        )

        period_start = movement.date_moved
        period_end = next_movement.date_moved if next_movement else now
        duration = period_end - period_start

        movement.period_start = period_start
        movement.period_end = period_end
        movement.days_spent = max(duration.days, 0)
        movement.duration_label = format_duration(duration)
        movement.is_current_stay = next_movement is None

    return list(reversed(movements_asc))


def find_shared_destination_item(source_item, to_warehouse):
    return (
        InventoryItem.objects.select_for_update()
        .filter(
            serial_number=source_item.serial_number,
            item_type=InventoryItem.TYPE_SHARED,
            current_warehouse=to_warehouse,
            quantity__gt=0,
        )
        .exclude(pk=source_item.pk)
        .first()
    )


def move_inventory_quantity(*, item, to_warehouse, quantity_to_move, moved_by, note):
    """
    Unique item:
        Move the whole item row.

    Shared item:
        Move partial or full quantity.
        If destination already has same shared serial, merge quantities.
        Otherwise create a new destination stock row.
    """
    from_warehouse = item.current_warehouse

    if item.current_warehouse_id == to_warehouse.id:
        raise ValueError("Source and destination warehouses cannot be the same.")

    if item.item_type == InventoryItem.TYPE_UNIQUE:
        movement = InventoryMovement.objects.create(
            item=item,
            from_warehouse=from_warehouse,
            to_warehouse=to_warehouse,
            quantity_moved=1,
            moved_by=moved_by,
            note=note,
        )

        item.current_warehouse = to_warehouse
        item.quantity = 1
        item.save(update_fields=["current_warehouse", "quantity"])
        return item, movement

    if quantity_to_move is None:
        quantity_to_move = item.quantity

    if quantity_to_move < 1:
        raise ValueError("Quantity to move must be at least 1.")

    if quantity_to_move > item.quantity:
        raise ValueError(
            f"Only {item.quantity} available for {item.serial_number}."
        )

    destination_item = find_shared_destination_item(item, to_warehouse)

    movement = InventoryMovement.objects.create(
        item=item,
        from_warehouse=from_warehouse,
        to_warehouse=to_warehouse,
        quantity_moved=quantity_to_move,
        moved_by=moved_by,
        note=note,
    )

    # Full quantity and no destination row:
    # move the current row to the destination warehouse.
    if quantity_to_move == item.quantity and destination_item is None:
        item.current_warehouse = to_warehouse
        item.save(update_fields=["current_warehouse"])
        return item, movement

    # Destination already has same shared serial, so merge into it.
    if destination_item:
        destination_item.quantity += quantity_to_move
        destination_item.save(update_fields=["quantity"])
    else:
        InventoryItem.objects.create(
            name=item.name,
            serial_number=item.serial_number,
            product_type=item.product_type,
            item_type=InventoryItem.TYPE_SHARED,
            quantity=quantity_to_move,
            current_warehouse=to_warehouse,
        )

    # Reduce source row. If this reaches 0, the row is inactive.
    item.quantity -= quantity_to_move
    item.save(update_fields=["quantity"])

    return item, movement


def create_delivery_note_for_movements(*, movements, form, created_by, note=None):
    if not movements:
        return None

    first_movement = movements[0]

    delivery_note = InventoryDeliveryNote.objects.create(
        from_warehouse=first_movement.from_warehouse,
        to_warehouse=first_movement.to_warehouse,
        recipient_name=form.cleaned_data["delivery_recipient_name"].strip(),
        recipient_email=(form.cleaned_data.get("delivery_recipient_email") or "").strip() or None,
        recipient_phone=(form.cleaned_data.get("delivery_recipient_phone") or "").strip() or None,
        recipient_organization=(form.cleaned_data.get("delivery_recipient_organization") or "").strip() or None,
        destination_address=(form.cleaned_data.get("delivery_destination_address") or "").strip() or None,
        note=note,
        created_by=created_by,
    )

    delivery_items = []

    for movement in movements:
        delivery_items.append(
            InventoryDeliveryNoteItem(
                delivery_note=delivery_note,
                movement=movement,
                item=movement.item,
                item_name=movement.item.name,
                serial_number=movement.item.serial_number,
                product_type=movement.item.product_type,
                quantity=movement.quantity_moved,
            )
        )

    InventoryDeliveryNoteItem.objects.bulk_create(delivery_items)
    return delivery_note


def user_can_access_delivery_note(user, delivery_note):
    if is_superadmin(user):
        return True

    user_org = getattr(user, "organization", None)

    if not user_org:
        return False

    return (
        getattr(delivery_note.from_warehouse, "organization_id", None) == user_org.id
        or getattr(delivery_note.to_warehouse, "organization_id", None) == user_org.id
    )


def get_delivery_note_for_user_or_404(request, pk):
    delivery_note = get_object_or_404(
        InventoryDeliveryNote.objects.select_related(
            "from_warehouse",
            "to_warehouse",
            "created_by",
        ),
        pk=pk,
    )

    if not user_can_access_delivery_note(request.user, delivery_note):
        return get_object_or_404(InventoryDeliveryNote.objects.none(), pk=pk)

    return delivery_note


def get_delivery_note_confirmation_url(request, delivery_note):
    return request.build_absolute_uri(
        reverse("inventory:delivery_note_receive", args=[delivery_note.token])
    )


def generate_delivery_note_pdf(delivery_note, request=None):
    confirmation_url = (
        get_delivery_note_confirmation_url(request, delivery_note)
        if request is not None
        else ""
    )

    html = render_to_string(
        "inventory/delivery_note_pdf.html",
        {
            "delivery_note": delivery_note,
            "delivery_items": delivery_note.items.all(),
            "confirmation_url": confirmation_url,
            "STATIC_ROOT": os.path.join(settings.BASE_DIR, "static"),
            "MEDIA_ROOT": os.path.join(settings.BASE_DIR, "media"),
        },
    )

    result = BytesIO()
    pdf = pisa.CreatePDF(src=html, dest=result)

    if pdf.err:
        return None

    return result.getvalue()


# =========================
# WAREHOUSES
# =========================

@login_required
def warehouses_page(request):
    user = request.user

    if not is_superadmin(user):
        return redirect("inventory:inventory_page")

    warehouses = Warehouse.objects.annotate(
        total_items=Sum("inventory_items__quantity")
    )

    total_warehouses = warehouses.count()

    total_inventory = (
        InventoryItem.objects
        .filter(quantity__gt=0)
        .aggregate(total=Sum("quantity"))["total"]
        or 0
    )

    labels = [w.name for w in warehouses]
    data = [w.total_items or 0 for w in warehouses]

    return render(
        request,
        "inventory/warehouses.html",
        {
            "warehouses": warehouses,
            "total_warehouses": total_warehouses,
            "total_inventory": total_inventory,
            "warehouse_labels": labels,
            "warehouse_data": data,
        },
    )


@login_required
def warehouse_create(request):
    if not is_superadmin(request.user):
        return redirect("inventory:inventory_page")

    if request.method == "POST":
        form = WarehouseForm(request.POST)

        if form.is_valid():
            form.save()

            notify(
                request.user,
                "New Warehouse",
                f"{form.cleaned_data['name']} warehouse has been created.",
                "success",
            )

            return redirect("inventory:warehouses_page")
    else:
        form = WarehouseForm()

    return render(request, "inventory/warehouse_form.html", {"form": form})


@login_required
def warehouse_update(request, pk):
    if not is_superadmin(request.user):
        return redirect("inventory:inventory_page")

    warehouse = get_object_or_404(Warehouse, pk=pk)

    if request.method == "POST":
        form = WarehouseForm(request.POST, instance=warehouse)

        if form.is_valid():
            form.save()

            notify(
                request.user,
                "Warehouse Update",
                f"{warehouse.name} warehouse has been updated.",
                "info",
            )

            return redirect("inventory:warehouses_page")
    else:
        form = WarehouseForm(instance=warehouse)

    return render(request, "inventory/warehouse_form.html", {"form": form})


@login_required
def warehouse_delete(request, pk):
    if not is_superadmin(request.user):
        return redirect("inventory:inventory_page")

    warehouse = get_object_or_404(Warehouse, pk=pk)
    warehouse.delete()

    notify(
        request.user,
        "Warehouse Deleted",
        f"{warehouse.name} warehouse has been deleted.",
        "warning",
    )

    return redirect("inventory:warehouses_page")


# =========================
# INVENTORY ITEMS
# =========================

@login_required
def item_create(request):
    allowed_warehouses = get_allowed_warehouses(request.user)

    if request.method == "POST":
        form = InventoryItemForm(request.POST)
        form.fields["current_warehouse"].queryset = allowed_warehouses

        if form.is_valid():
            with transaction.atomic():
                item = form.save(commit=False)

                if item.item_type == InventoryItem.TYPE_UNIQUE:
                    item.quantity = 1
                    item.save()

                    InventoryMovement.objects.create(
                        item=item,
                        to_warehouse=item.current_warehouse,
                        quantity_moved=1,
                        moved_by=request.user,
                        note="Initial assignment",
                    )

                else:
                    quantity_added = item.quantity

                    existing_item = (
                        InventoryItem.objects.select_for_update()
                        .filter(
                            serial_number=item.serial_number,
                            item_type=InventoryItem.TYPE_SHARED,
                            current_warehouse=item.current_warehouse,
                            quantity__gt=0,
                        )
                        .first()
                    )

                    if existing_item:
                        existing_item.quantity += quantity_added
                        existing_item.save(update_fields=["quantity"])
                        item = existing_item
                    else:
                        item.save()

                    InventoryMovement.objects.create(
                        item=item,
                        to_warehouse=item.current_warehouse,
                        quantity_moved=quantity_added,
                        moved_by=request.user,
                        note="Initial assignment",
                    )

            notify(
                request.user,
                "New Item",
                f"{item.serial_number}({item.name}) has been created.",
                "success",
            )

            return redirect("inventory:inventory_page")
    else:
        form = InventoryItemForm(
            initial={
                "item_type": InventoryItem.TYPE_UNIQUE,
                "quantity": 1,
            }
        )
        form.fields["current_warehouse"].queryset = allowed_warehouses

    return render(request, "inventory/item_form.html", {"form": form})


@login_required
def bulk_item_create(request):
    user = request.user
    user_is_superadmin = is_superadmin(user)
    allowed_warehouses = get_allowed_warehouses(user)

    if request.method == "POST":
        form = BulkInventoryItemForm(request.POST, request.FILES)
        form.fields["current_warehouse"].queryset = allowed_warehouses

        if form.is_valid():
            warehouse = form.cleaned_data["current_warehouse"]

            created_count = 0
            updated_count = 0
            total_quantity_added = 0

            with transaction.atomic():
                for row in form.cleaned_rows:
                    try:
                        if row["item_type"] == InventoryItem.TYPE_UNIQUE:
                            item = InventoryItem.objects.create(
                                name=row["name"],
                                serial_number=row["serial_number"],
                                product_type=row["product_type"],
                                item_type=InventoryItem.TYPE_UNIQUE,
                                quantity=1,
                                current_warehouse=warehouse,
                            )

                            InventoryMovement.objects.create(
                                item=item,
                                to_warehouse=warehouse,
                                quantity_moved=1,
                                moved_by=request.user,
                                note="Initial bulk assignment",
                            )

                            created_count += 1
                            total_quantity_added += 1

                        else:
                            quantity_added = row["quantity"]

                            item = (
                                InventoryItem.objects.select_for_update()
                                .filter(
                                    serial_number=row["serial_number"],
                                    item_type=InventoryItem.TYPE_SHARED,
                                    current_warehouse=warehouse,
                                    quantity__gt=0,
                                )
                                .first()
                            )

                            if item:
                                item.quantity += quantity_added
                                item.save(update_fields=["quantity"])
                                updated_count += 1
                            else:
                                item = InventoryItem.objects.create(
                                    name=row["name"],
                                    serial_number=row["serial_number"],
                                    product_type=row["product_type"],
                                    item_type=InventoryItem.TYPE_SHARED,
                                    quantity=quantity_added,
                                    current_warehouse=warehouse,
                                )
                                created_count += 1

                            InventoryMovement.objects.create(
                                item=item,
                                to_warehouse=warehouse,
                                quantity_moved=quantity_added,
                                moved_by=request.user,
                                note="Initial bulk assignment",
                            )

                            total_quantity_added += quantity_added

                    except IntegrityError:
                        form.add_error(
                            "csv_data",
                            f"Duplicate serial detected: {row.get('serial_number')}"
                        )
                        continue

            notify(
                request.user,
                "Bulk Inventory Added",
                (
                    f"{created_count} inventory row(s) created, "
                    f"{updated_count} shared row(s) updated, "
                    f"{total_quantity_added} total unit(s) added."
                ),
                "success",
            )

            return redirect("inventory:inventory_page")

    else:
        sample_entries = "SM-001\nSM-002\nSM-003"

        form = BulkInventoryItemForm(
            initial={
                "default_name": "Smart Meter",
                "default_product_type": "Meter",
                "default_item_type": InventoryItem.TYPE_UNIQUE,
                "default_quantity": 1,
                "csv_data": sample_entries,
            }
        )

        form.fields["current_warehouse"].queryset = allowed_warehouses

    return render(request, "inventory/bulk_item_form.html", {"form": form})


@login_required
def item_update(request, pk):
    item = get_object_or_404(get_allowed_inventory_items(request.user), pk=pk)

    if request.method == "POST":
        form = InventoryItemForm(request.POST, instance=item)
        form.fields["current_warehouse"].queryset = get_allowed_warehouses(request.user)

        if form.is_valid():
            form.save()

            notify(
                request.user,
                "Item Updated",
                f"{item.serial_number}({item.name}) has been updated.",
                "info",
            )

            return redirect("inventory:inventory_page")
    else:
        form = InventoryItemForm(instance=item)
        form.fields["current_warehouse"].queryset = get_allowed_warehouses(request.user)

    return render(request, "inventory/item_form.html", {"form": form})


@login_required
def item_delete(request, pk):
    item = get_object_or_404(get_allowed_inventory_items(request.user), pk=pk)
    item.delete()

    notify(
        request.user,
        "Item Deleted",
        f"{item.serial_number}({item.name}) has been deleted.",
        "warning",
    )

    return redirect("inventory:inventory_page")


@login_required
def inventory_page(request):
    user = request.user
    user_is_superadmin = is_superadmin(user)
    is_htmx = request.headers.get("HX-Request") == "true"

    qs = InventoryItem.objects.select_related("current_warehouse").filter(
        quantity__gt=0
    )

    if not user_is_superadmin:
        qs = qs.filter(current_warehouse__organization=user.organization)

    search_query = request.GET.get("q", "").strip()

    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(serial_number__icontains=search_query)
            | Q(product_type__icontains=search_query)
            | Q(item_type__icontains=search_query)
        )

    org_filter = request.GET.get("org", "")
    warehouse_filter = request.GET.get("warehouse", "")
    item_type_filter = request.GET.get("item_type", "")
    period = request.GET.get("period", "all")

    if item_type_filter in {
        InventoryItem.TYPE_UNIQUE,
        InventoryItem.TYPE_SHARED,
    }:
        qs = qs.filter(item_type=item_type_filter)

    if user_is_superadmin and org_filter:
        qs = qs.filter(current_warehouse__organization_id=org_filter)

    if warehouse_filter:
        qs = qs.filter(current_warehouse_id=warehouse_filter)

    today = timezone.now().date()

    if period == "1d":
        qs = qs.filter(date_added__gte=today - timedelta(days=1))
    elif period == "3d":
        qs = qs.filter(date_added__gte=today - timedelta(days=3))
    elif period == "7d":
        qs = qs.filter(date_added__gte=today - timedelta(days=7))
    elif period == "14d":
        qs = qs.filter(date_added__gte=today - timedelta(days=14))
    elif period == "30d":
        qs = qs.filter(date_added__gte=today - timedelta(days=30))
    elif period == "60d":
        qs = qs.filter(date_added__gte=today - timedelta(days=60))
    elif period == "90d":
        qs = qs.filter(date_added__gte=today - timedelta(days=90))
    elif period == "180d":
        qs = qs.filter(date_added__gte=today - timedelta(days=180))
    elif period == "365d":
        qs = qs.filter(date_added__gte=today - timedelta(days=365))

    SORT_MAP = {
        "name": "name",
        "serial": "serial_number",
        "type": "product_type",
        "tracking_type": "item_type",
        "quantity": "quantity",
        "warehouse": "current_warehouse__name",
        "days": "date_added",
    }

    inventory_fields = [
        ("Name", "name"),
        ("Serial Number", "serial"),
        ("Product Type", "type"),
        ("Tracking Type", "tracking_type"),
        ("Quantity", "quantity"),
        ("Warehouse", "warehouse"),
        ("Days in Warehouse", "days"),
        ("Actions", "actions"),
    ]

    sort = request.GET.get("sort", "name")
    direction = request.GET.get("dir", "asc")

    sort_field = SORT_MAP.get(sort, "name")

    if direction == "desc":
        sort_field = f"-{sort_field}"

    qs = qs.order_by(sort_field)
    total_results = qs.count()

    next_dirs = {}

    for _, field in inventory_fields:
        if field == sort:
            next_dirs[field] = "desc" if direction == "asc" else "asc"
        else:
            next_dirs[field] = "asc"

    organizations = Organization.objects.all() if user_is_superadmin else None
    warehouses = get_allowed_warehouses(user)

    allowed_page_sizes = [10, 25, 50, 100]

    try:
        page_size = int(request.GET.get("page_size", 10))
    except (TypeError, ValueError):
        page_size = 10

    if page_size not in allowed_page_sizes:
        page_size = 10

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    table_context = {
        "page_obj": page_obj,
        "page_size": page_size,
        "page_size_options": allowed_page_sizes,
        "search_query": search_query,
        "current_sort": sort,
        "current_dir": direction,
        "inventory_fields": inventory_fields,
        "next_dirs": next_dirs,
        "org_filter": org_filter,
        "warehouse_filter": warehouse_filter,
        "item_type_filter": item_type_filter,
        "period": period,
        "organizations": organizations,
        "warehouses": warehouses,
        "is_superadmin": user_is_superadmin,
        "total_results": total_results,
    }

    if is_htmx:
        return render(
            request,
            "partials/inventory_table.html",
            table_context,
        )

    total_items = qs.aggregate(total=Sum("quantity"))["total"] or 0

    unique_items = qs.filter(
        item_type=InventoryItem.TYPE_UNIQUE
    ).count()

    unique_units = qs.filter(
        item_type=InventoryItem.TYPE_UNIQUE
    ).aggregate(total=Sum("quantity"))["total"] or 0

    shared_rows = qs.filter(
        item_type=InventoryItem.TYPE_SHARED
    ).count()

    shared_units = qs.filter(
        item_type=InventoryItem.TYPE_SHARED
    ).aggregate(total=Sum("quantity"))["total"] or 0

    last_30_days = timezone.now().date() - timedelta(days=30)

    new_items_30 = qs.filter(
        date_added__gte=last_30_days
    ).aggregate(total=Sum("quantity"))["total"] or 0

    warehouse_qs = (
        qs.values("current_warehouse__name")
        .annotate(total=Sum("quantity"))
        .order_by("current_warehouse__name")
    )

    warehouse_labels = [x["current_warehouse__name"] for x in warehouse_qs]
    warehouse_data = [x["total"] or 0 for x in warehouse_qs]

    growth_qs = (
        qs.annotate(month=TruncMonth("date_added"))
        .values("month")
        .annotate(count=Sum("quantity"))
        .order_by("month")
    )

    growth_labels = []
    growth_data = []
    running_total = 0

    for row in growth_qs:
        running_total += row["count"] or 0
        growth_labels.append(row["month"].strftime("%b %Y"))
        growth_data.append(running_total)

    return render(
        request,
        "inventory/inventory.html",
        {
            **table_context,
            "total_items": total_items,
            "new_items_30": new_items_30,
            "warehouse_labels": warehouse_labels,
            "warehouse_data": warehouse_data,
            "growth_labels": growth_labels,
            "growth_data": growth_data,
            "unique_items": unique_items,
            "unique_units": unique_units,
            "shared_rows": shared_rows,
            "shared_units": shared_units,
        },
    )


@login_required
def inventory_detail(request, pk):
    item = get_object_or_404(
        get_allowed_inventory_items(request.user),
        pk=pk,
    )

    user = request.user
    user_is_superadmin = is_superadmin(user)

    serial_items_qs = (
        InventoryItem.objects
        .select_related("current_warehouse")
        .filter(
            serial_number=item.serial_number,
            quantity__gt=0,
        )
    )

    if not user_is_superadmin:
        serial_items_qs = serial_items_qs.filter(
            current_warehouse__organization=user.organization
        )

    warehouse_breakdown = (
        serial_items_qs
        .values("current_warehouse__name")
        .annotate(total_quantity=Sum("quantity"))
        .order_by("current_warehouse__name")
    )

    total_quantity_for_serial = (
        serial_items_qs.aggregate(total=Sum("quantity"))["total"] or 0
    )

    movements_qs = (
        InventoryMovement.objects
        .select_related(
            "item",
            "from_warehouse",
            "to_warehouse",
            "moved_by",
        )
        .filter(item__serial_number=item.serial_number)
    )

    if not user_is_superadmin:
        movements_qs = movements_qs.filter(
            Q(from_warehouse__organization=user.organization)
            | Q(to_warehouse__organization=user.organization)
        )

    timeline_movements = build_timeline_movements(movements_qs)

    paginator = Paginator(timeline_movements, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "inventory/inventory_detail.html",
        {
            "item": item,
            "page_obj": page_obj,
            "warehouse_breakdown": warehouse_breakdown,
            "total_quantity_for_serial": total_quantity_for_serial,
        },
    )


# =========================
# MOVE INVENTORY ITEM
# =========================

@login_required
def move_item(request, pk):
    item = get_object_or_404(
        get_allowed_inventory_items(request.user),
        pk=pk,
        quantity__gt=0,
    )

    allowed_warehouses = get_allowed_warehouses(request.user)
    db_alias = router.db_for_write(InventoryItem)

    if request.method == "POST":
        form = InventoryMoveForm(
            request.POST,
            item=item,
            allowed_warehouses=allowed_warehouses,
        )

        if form.is_valid():
            to_warehouse = form.cleaned_data["to_warehouse"]
            quantity_to_move = form.cleaned_data.get("quantity_to_move")
            note = form.cleaned_data.get("note") or "Inventory movement"
            delivery_note = None

            try:
                with transaction.atomic(using=db_alias):
                    locked_item = (
                        InventoryItem.objects
                        .using(db_alias)
                        .select_for_update()
                        .select_related("current_warehouse")
                        .get(pk=item.pk, quantity__gt=0)
                    )

                    if locked_item.item_type == InventoryItem.TYPE_UNIQUE:
                        quantity_to_move = 1
                    elif quantity_to_move is None:
                        quantity_to_move = locked_item.quantity

                    moved_item, movement = move_inventory_quantity(
                        item=locked_item,
                        to_warehouse=to_warehouse,
                        quantity_to_move=quantity_to_move,
                        moved_by=request.user,
                        note=note,
                    )

                    if form.cleaned_data.get("create_delivery_note"):
                        delivery_note = create_delivery_note_for_movements(
                            movements=[movement],
                            form=form,
                            created_by=request.user,
                            note=note,
                        )

                notify(
                    request.user,
                    "Item Moved",
                    (
                        f"{quantity_to_move} unit(s) of "
                        f"{item.serial_number} ({item.name}) moved to "
                        f"{to_warehouse.name}."
                    ),
                    "info",
                )

                if delivery_note:
                    return redirect(
                        "inventory:delivery_note_detail",
                        pk=delivery_note.pk,
                    )

                return redirect("inventory:inventory_page")

            except InventoryItem.DoesNotExist:
                form.add_error(
                    None,
                    "This item is no longer available for movement.",
                )

            except ValueError as exc:
                form.add_error(None, str(exc))

    else:
        form = InventoryMoveForm(
            item=item,
            allowed_warehouses=allowed_warehouses,
        )

    return render(
        request,
        "inventory/move_item.html",
        {
            "item": item,
            "form": form,
        },
    )


@login_required
def bulk_move_items(request):
    user = request.user
    user_is_superadmin = is_superadmin(user)
    allowed_warehouses = get_allowed_warehouses(user)
    db_alias = router.db_for_write(InventoryItem)

    if request.method == "POST":
        form = BulkInventoryMoveForm(
            request.POST,
            allowed_warehouses=allowed_warehouses,
        )

        if form.is_valid():
            move_entries = form.cleaned_data["serial_numbers"]
            from_warehouse = form.cleaned_data["from_warehouse"]
            to_warehouse = form.cleaned_data["to_warehouse"]
            note = form.cleaned_data.get("note") or "Bulk inventory movement"

            serial_numbers = [
                entry["serial_number"]
                for entry in move_entries
            ]

            errors = []
            delivery_note = None

            try:
                with transaction.atomic(using=db_alias):
                    items_qs = (
                        InventoryItem.objects
                        .using(db_alias)
                        .select_for_update()
                        .select_related("current_warehouse")
                        .filter(
                            serial_number__in=serial_numbers,
                            current_warehouse=from_warehouse,
                            quantity__gt=0,
                        )
                    )

                    if not user_is_superadmin:
                        items_qs = items_qs.filter(
                            current_warehouse__organization=user.organization
                        )

                    source_items = list(items_qs)
                    items_by_serial = defaultdict(list)

                    for item in source_items:
                        items_by_serial[item.serial_number].append(item)

                    for entry in move_entries:
                        serial_number = entry["serial_number"]
                        requested_quantity = entry["quantity"]
                        matches = items_by_serial.get(serial_number, [])

                        if not matches:
                            errors.append(
                                f"{serial_number}: not found in {from_warehouse.name}, or not accessible."
                            )
                            continue

                        if len(matches) > 1:
                            errors.append(
                                f"{serial_number}: multiple active rows exist in {from_warehouse.name}. "
                                "Merge or clean duplicates first."
                            )
                            continue

                        item = matches[0]

                        if item.current_warehouse_id == to_warehouse.id:
                            errors.append(
                                f"{serial_number}: source and destination warehouse are the same."
                            )
                            continue

                        if item.item_type == InventoryItem.TYPE_UNIQUE:
                            if requested_quantity and requested_quantity != 1:
                                errors.append(
                                    f"{serial_number}: unique items can only move quantity 1."
                                )
                        else:
                            quantity_to_move = requested_quantity or item.quantity

                            if quantity_to_move < 1:
                                errors.append(
                                    f"{serial_number}: quantity must be at least 1."
                                )

                            if quantity_to_move > item.quantity:
                                errors.append(
                                    f"{serial_number}: only {item.quantity} available in {from_warehouse.name}."
                                )

                    if errors:
                        form.add_error("serial_numbers", errors)
                    else:
                        moved_rows = 0
                        moved_quantity = 0
                        movements = []

                        for entry in move_entries:
                            item = items_by_serial[entry["serial_number"]][0]

                            if item.item_type == InventoryItem.TYPE_UNIQUE:
                                quantity_to_move = 1
                            else:
                                quantity_to_move = entry["quantity"] or item.quantity

                            moved_item, movement = move_inventory_quantity(
                                item=item,
                                to_warehouse=to_warehouse,
                                quantity_to_move=quantity_to_move,
                                moved_by=request.user,
                                note=note,
                            )

                            movements.append(movement)
                            moved_rows += 1
                            moved_quantity += quantity_to_move

                        if form.cleaned_data.get("create_delivery_note"):
                            delivery_note = create_delivery_note_for_movements(
                                movements=movements,
                                form=form,
                                created_by=request.user,
                                note=note,
                            )

                        notify(
                            request.user,
                            "Bulk Inventory Movement",
                            (
                                f"{moved_rows} serial row(s), "
                                f"{moved_quantity} total unit(s), moved from "
                                f"{from_warehouse.name} to {to_warehouse.name}."
                            ),
                            "success",
                        )

                        if delivery_note:
                            return redirect(
                                "inventory:delivery_note_detail",
                                pk=delivery_note.pk,
                            )

                        return redirect("inventory:inventory_page")

            except ValueError as exc:
                form.add_error(None, str(exc))

    else:
        form = BulkInventoryMoveForm(
            allowed_warehouses=allowed_warehouses,
        )

    return render(
        request,
        "inventory/bulk_move_items.html",
        {
            "form": form,
        },
    )

# =========================
# DELIVERY NOTES
# =========================

@login_required
def delivery_note_detail(request, pk):
    delivery_note = get_delivery_note_for_user_or_404(request, pk)

    return render(
        request,
        "inventory/delivery_note_detail.html",
        {
            "delivery_note": delivery_note,
            "delivery_items": delivery_note.items.all(),
            "confirmation_url": get_delivery_note_confirmation_url(request, delivery_note),
        },
    )


@login_required
def delivery_note_pdf(request, pk):
    delivery_note = get_delivery_note_for_user_or_404(request, pk)
    pdf = generate_delivery_note_pdf(delivery_note, request=request)

    if not pdf:
        return HttpResponse("Could not generate delivery note PDF", status=500)

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="delivery-note-{delivery_note.delivery_number}.pdf"'
    )
    return response


@login_required
def delivery_note_email(request, pk):
    delivery_note = get_delivery_note_for_user_or_404(request, pk)

    if request.method != "POST":
        return redirect("inventory:delivery_note_detail", pk=delivery_note.pk)

    if not delivery_note.recipient_email:
        notify(
            request.user,
            "Delivery Note Email Failed",
            "This delivery note does not have a receiver email address.",
            "error",
        )
        return redirect("inventory:delivery_note_detail", pk=delivery_note.pk)

    pdf = generate_delivery_note_pdf(delivery_note, request=request)

    if not pdf:
        notify(
            request.user,
            "Delivery Note Email Failed",
            "Could not generate the delivery note PDF.",
            "error",
        )
        return redirect("inventory:delivery_note_detail", pk=delivery_note.pk)

    html_body = render_to_string(
        "inventory/delivery_note_email.html",
        {
            "delivery_note": delivery_note,
            "delivery_items": delivery_note.items.all(),
            "confirmation_url": get_delivery_note_confirmation_url(request, delivery_note),
        },
    )
    text_body = strip_tags(html_body)

    msg = EmailMultiAlternatives(
        subject=f"Delivery Note {delivery_note.delivery_number}",
        body=text_body,
        from_email=None,
        to=[delivery_note.recipient_email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.attach(
        f"delivery-note-{delivery_note.delivery_number}.pdf",
        pdf,
        "application/pdf",
    )
    msg.send()

    notify(
        request.user,
        "Delivery Note Sent",
        f"Delivery note was sent to {delivery_note.recipient_email}.",
        "success",
    )

    return redirect("inventory:delivery_note_detail", pk=delivery_note.pk)


def delivery_note_receive(request, token):
    delivery_note = get_object_or_404(
        InventoryDeliveryNote.objects.select_related(
            "from_warehouse",
            "to_warehouse",
            "created_by",
        ),
        token=token,
    )

    if request.method == "POST" and not delivery_note.is_received:
        form = DeliveryNoteReceiveForm(request.POST)

        if form.is_valid():
            delivery_note.received_by_name = form.cleaned_data["received_by_name"].strip()
            delivery_note.receiver_note = (form.cleaned_data.get("receiver_note") or "").strip() or None
            delivery_note.received_in_good_condition = form.cleaned_data["received_in_good_condition"]
            delivery_note.received_at = timezone.now()
            delivery_note.save(
                update_fields=[
                    "received_by_name",
                    "receiver_note",
                    "received_in_good_condition",
                    "received_at",
                ]
            )

            return redirect("inventory:delivery_note_received", token=delivery_note.token)
    else:
        form = DeliveryNoteReceiveForm(initial={
            "received_by_name": delivery_note.recipient_name,
        })

    return render(
        request,
        "inventory/delivery_note_receive.html",
        {
            "delivery_note": delivery_note,
            "delivery_items": delivery_note.items.all(),
            "form": form,
        },
    )


def delivery_note_received(request, token):
    delivery_note = get_object_or_404(
        InventoryDeliveryNote.objects.select_related(
            "from_warehouse",
            "to_warehouse",
            "created_by",
        ),
        token=token,
    )

    return render(
        request,
        "inventory/delivery_note_received.html",
        {
            "delivery_note": delivery_note,
            "delivery_items": delivery_note.items.all(),
        },
    )

@login_required
def delivery_note_list(request):
    user = request.user
    user_is_superadmin = is_superadmin(user)

    qs = (
        InventoryDeliveryNote.objects
        .select_related(
            "from_warehouse",
            "to_warehouse",
            "created_by",
        )
        .prefetch_related("items")
        .annotate(total_quantity=Sum("items__quantity"))
    )

    if not user_is_superadmin:
        qs = qs.filter(
            Q(from_warehouse__organization=user.organization)
            | Q(to_warehouse__organization=user.organization)
            | Q(created_by=user)
        ).distinct()

    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    from_warehouse_filter = request.GET.get("from_warehouse", "").strip()
    to_warehouse_filter = request.GET.get("to_warehouse", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if search_query:
        search_filter = (
            Q(recipient_name__icontains=search_query)
            | Q(recipient_email__icontains=search_query)
            | Q(recipient_phone__icontains=search_query)
            | Q(recipient_organization__icontains=search_query)
            | Q(destination_address__icontains=search_query)
            | Q(from_warehouse__name__icontains=search_query)
            | Q(to_warehouse__name__icontains=search_query)
            | Q(items__serial_number__icontains=search_query)
            | Q(items__item_name__icontains=search_query)
            | Q(items__product_type__icontains=search_query)
        )

        if search_query.isdigit():
            search_filter |= Q(id=int(search_query))

        qs = qs.filter(search_filter).distinct()

    if status_filter == "pending":
        qs = qs.filter(received_at__isnull=True)

    elif status_filter == "confirmed":
        qs = qs.filter(
            received_at__isnull=False,
            received_in_good_condition=True,
        )

    elif status_filter == "issue":
        qs = qs.filter(
            received_at__isnull=False,
            received_in_good_condition=False,
        )

    if from_warehouse_filter:
        qs = qs.filter(from_warehouse_id=from_warehouse_filter)

    if to_warehouse_filter:
        qs = qs.filter(to_warehouse_id=to_warehouse_filter)

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)

    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    total_results = qs.count()
    total_units = qs.aggregate(total=Sum("items__quantity"))["total"] or 0
    pending_count = qs.filter(received_at__isnull=True).count()
    confirmed_count = qs.filter(
        received_at__isnull=False,
        received_in_good_condition=True,
    ).count()

    sort_map = {
        "number": "id",
        "recipient": "recipient_name",
        "from": "from_warehouse__name",
        "to": "to_warehouse__name",
        "created": "created_at",
        "received": "received_at",
        "quantity": "total_quantity",
    }

    sort = request.GET.get("sort", "created")
    direction = request.GET.get("dir", "desc")

    sort_field = sort_map.get(sort, "created_at")

    if direction == "desc":
        sort_field = f"-{sort_field}"

    qs = qs.order_by(sort_field, "-id")

    next_dirs = {}

    for field in sort_map:
        if field == sort:
            next_dirs[field] = "desc" if direction == "asc" else "asc"
        else:
            next_dirs[field] = "asc"

    allowed_page_sizes = [10, 25, 50, 100]

    try:
        page_size = int(request.GET.get("page_size", 10))
    except (TypeError, ValueError):
        page_size = 10

    if page_size not in allowed_page_sizes:
        page_size = 10

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))

    warehouses = get_allowed_warehouses(user)

    return render(
        request,
        "inventory/delivery_note_list.html",
        {
            "page_obj": page_obj,
            "page_size": page_size,
            "page_size_options": allowed_page_sizes,
            "search_query": search_query,
            "status_filter": status_filter,
            "from_warehouse_filter": from_warehouse_filter,
            "to_warehouse_filter": to_warehouse_filter,
            "date_from": date_from,
            "date_to": date_to,
            "warehouses": warehouses,
            "total_results": total_results,
            "total_units": total_units,
            "pending_count": pending_count,
            "confirmed_count": confirmed_count,
            "current_sort": sort,
            "current_dir": direction,
            "next_dirs": next_dirs,
            "is_superadmin": user_is_superadmin,
        },
    )