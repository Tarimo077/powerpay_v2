from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from inventory.models import InventoryItem, Warehouse

from .models import MaintenanceRecord, MaintenanceStatusUpdate

# Warehouse used to hold items that are under maintenance.
MAINTENANCE_WAREHOUSE_ID = getattr(settings, "MAINTENANCE_WAREHOUSE_ID", 7)


class MaintenanceWarehouseMissing(Exception):
    """Raised when the configured maintenance warehouse does not exist."""


def is_superadmin(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) == "superadmin")
    )


def get_maintenance_warehouse():
    try:
        return Warehouse.objects.get(pk=MAINTENANCE_WAREHOUSE_ID)
    except Warehouse.DoesNotExist as exc:
        raise MaintenanceWarehouseMissing(
            f"Maintenance warehouse with id={MAINTENANCE_WAREHOUSE_ID} does not exist."
        ) from exc


def is_maintenance_warehouse(warehouse):
    if warehouse is None:
        return False

    warehouse_id = getattr(warehouse, "id", warehouse)
    return str(warehouse_id) == str(MAINTENANCE_WAREHOUSE_ID)


def get_user_maintenance_records(user):
    """
    Superadmins see everything.

    Everyone else sees records whose organization snapshot, source warehouse
    organization, or the item's current warehouse organization matches their
    own organization.
    """
    qs = (
        MaintenanceRecord.objects
        .select_related(
            "item",
            "item__current_warehouse",
            "organization",
            "source_warehouse",
            "created_by",
        )
    )

    if is_superadmin(user):
        return qs

    org_id = getattr(user, "organization_id", None)

    if not org_id:
        return qs.none()

    return qs.filter(
        Q(organization_id=org_id)
        | Q(source_warehouse__organization_id=org_id)
        | Q(item__current_warehouse__organization_id=org_id)
    ).distinct()


def log_status_change(record, status, note=None, user=None):
    return MaintenanceStatusUpdate.objects.create(
        record=record,
        status=status,
        note=note or None,
        changed_by=user if user and user.is_authenticated else None,
    )


def open_record_for_item(item):
    return (
        MaintenanceRecord.objects
        .filter(item=item, status__in=MaintenanceRecord.OPEN_STATUSES)
        .first()
    )


def create_maintenance_record(
    *,
    item,
    user,
    reported_fault=None,
    priority=MaintenanceRecord.PRIORITY_NORMAL,
    movement=None,
    source_warehouse=None,
    status=MaintenanceRecord.STATUS_RECEIVED,
):
    """
    Creates a maintenance record for an item that is already sitting in the
    maintenance warehouse (movement handled by the caller).
    """
    source = source_warehouse or (movement.from_warehouse if movement else None)

    record = MaintenanceRecord.objects.create(
        item=item,
        organization=getattr(source, "organization", None),
        source_warehouse=source,
        item_name=item.name,
        serial_number=item.serial_number,
        product_type=item.product_type,
        status=status,
        priority=priority,
        reported_fault=reported_fault or None,
        movement_in=movement,
        created_by=user if user and user.is_authenticated else None,
    )

    log_status_change(record, status, "Item received for maintenance.", user)
    return record


def send_item_to_maintenance(
    *,
    item,
    user,
    reported_fault=None,
    priority=MaintenanceRecord.PRIORITY_NORMAL,
    note=None,
):
    """
    Moves one unit of the item into the maintenance warehouse and creates the
    matching maintenance record.
    """
    from inventory.views import move_inventory_quantity

    maintenance_warehouse = get_maintenance_warehouse()
    source_warehouse = item.current_warehouse

    if item.current_warehouse_id == maintenance_warehouse.id:
        moved_item, movement = item, None
    else:
        quantity = 1 if item.item_type == InventoryItem.TYPE_UNIQUE else 1
        moved_item, movement = move_inventory_quantity(
            item=item,
            to_warehouse=maintenance_warehouse,
            quantity_to_move=quantity,
            moved_by=user,
            note=note or "Sent to maintenance",
        )

    return create_maintenance_record(
        item=moved_item,
        user=user,
        reported_fault=reported_fault,
        priority=priority,
        movement=movement,
        source_warehouse=source_warehouse,
    )


def create_records_for_movements(*, movements, user, note=None):
    """
    Called after an inventory move (single or bulk) that landed items in the
    maintenance warehouse. Creates one record per moved item.
    """
    created = []

    for movement in movements:
        if not is_maintenance_warehouse(movement.to_warehouse_id):
            continue

        item = movement.item

        if item is None:
            continue

        if open_record_for_item(item):
            continue

        created.append(
            create_maintenance_record(
                item=item,
                user=user,
                reported_fault=note,
                movement=movement,
                source_warehouse=movement.from_warehouse,
            )
        )

    return created


def close_record(record, *, status, user=None, note=None, return_warehouse=None):
    """
    Applies a closing status and optionally moves the item back out of the
    maintenance warehouse.
    """
    from inventory.views import move_inventory_quantity

    movement = None

    if return_warehouse and record.item and record.item.current_warehouse_id != return_warehouse.id:
        _, movement = move_inventory_quantity(
            item=record.item,
            to_warehouse=return_warehouse,
            quantity_to_move=1,
            moved_by=user,
            note=note or f"Returned from maintenance ({record.reference})",
        )

    record.status = status
    record.closed_at = timezone.now()

    if movement:
        record.movement_out = movement

    record.save(update_fields=["status", "closed_at", "movement_out", "updated_at"])
    log_status_change(record, status, note, user)
    return record
