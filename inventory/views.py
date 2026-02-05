from datetime import timedelta
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db.models import Q
from .models import InventoryItem, Warehouse
from django.contrib.auth.decorators import login_required
from .forms import WarehouseForm, InventoryItemForm, InventoryMoveForm


# =========================
# WAREHOUSES
# =========================
@login_required
def warehouses_page(request):
    user = request.user
    if user.role != "superadmin":
        return redirect("inventory_page")

    warehouses = Warehouse.objects.annotate(
        total_items=Count("inventory_items")
    )

    total_warehouses = warehouses.count()
    total_inventory = InventoryItem.objects.count()

    labels = [w.name for w in warehouses]
    data = [w.total_items for w in warehouses]

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
    if request.method == "POST":
        form = WarehouseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("warehouse_page")
    else:
        form = WarehouseForm()

    return render(request, "inventory/warehouse_form.html", {"form": form})


@login_required
def warehouse_update(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)

    if request.method == "POST":
        form = WarehouseForm(request.POST, instance=warehouse)
        if form.is_valid():
            form.save()
            return redirect("warehouse_page")
    else:
        form = WarehouseForm(instance=warehouse)

    return render(request, "inventory/warehouse_form.html", {"form": form})


@login_required
def warehouse_delete(request, pk):
    warehouse = get_object_or_404(Warehouse, pk=pk)
    warehouse.delete()
    return redirect("warehouse_page")


# =========================
# INVENTORY ITEMS
# =========================

@login_required
def item_create(request):
    if request.method == "POST":
        form = InventoryItemForm(request.POST)
        if form.is_valid():
            item = form.save()

            # create initial movement record
            InventoryMovement.objects.create(
                item=item,
                to_warehouse=item.current_warehouse,
                moved_by=request.user,
                note="Initial assignment"
            )
            return redirect("inventory_page")
    else:
        form = InventoryItemForm()

    return render(request, "inventory/item_form.html", {"form": form})


@login_required
def item_update(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)

    if request.method == "POST":
        form = InventoryItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            return redirect("inventory_page")
    else:
        form = InventoryItemForm(instance=item)

    return render(request, "inventory/item_form.html", {"form": form})


@login_required
def item_delete(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    item.delete()
    return redirect("inventory_page")

@login_required
def inventory_page(request):
    user = request.user
    is_superadmin = user.role == "superadmin"
    is_htmx = request.headers.get("HX-Request") == "true"

    # ---------------- BASE QUERYSET ----------------
    qs = InventoryItem.objects.select_related("current_warehouse")
    if not is_superadmin:
        qs = qs.filter(current_warehouse__organization=user.organization)

    # ---------------- SEARCH ----------------
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query) |
            Q(serial_number__icontains=search_query) |
            Q(product_type__icontains=search_query)
        )

    # ---------------- SORTING ----------------
    SORT_MAP = {
        "name": "name",
        "serial": "serial_number",
        "type": "product_type",
        "warehouse": "current_warehouse__name",
        "days": "date_added",
    }

    inventory_fields = [
        ("Name", "name"),
        ("Serial Number", "serial"),
        ("Product Type", "type"),
        ("Warehouse", "warehouse"),
        ("Days in Warehouse", "days"),
        ("Actions", "actions")
    ]

    sort = request.GET.get("sort", "name")   # ✅ valid default
    direction = request.GET.get("dir", "asc")

    sort_field = SORT_MAP.get(sort, "name")
    if direction == "desc":
        sort_field = f"-{sort_field}"

    qs = qs.order_by(sort_field)

    # ---------------- NEXT SORT DIRECTIONS ----------------
    next_dirs = {}
    for _, field in inventory_fields:
        if field == sort:
            next_dirs[field] = "desc" if direction == "asc" else "asc"
        else:
            next_dirs[field] = "asc"

    # ---------------- PAGINATION ----------------
    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # ---------------- HTMX RESPONSE ----------------
    if is_htmx:
        return render(
            request,
            "partials/inventory_table.html",
            {
                "page_obj": page_obj,
                "search_query": search_query,
                "current_sort": sort,
                "current_dir": direction,
                "inventory_fields": inventory_fields,
                "next_dirs": next_dirs,
            },
        )

    # ---------------- STATS ----------------
    total_items = qs.count()
    last_30_days = timezone.now().date() - timedelta(days=30)
    new_items_30 = qs.filter(date_added__gte=last_30_days).count()

    # ---------------- ITEMS PER WAREHOUSE ----------------
    warehouse_qs = (
        qs.values("current_warehouse__name")
        .annotate(total=Count("id"))
        .order_by("current_warehouse__name")
    )

    warehouse_labels = [x["current_warehouse__name"] for x in warehouse_qs]
    warehouse_data = [x["total"] for x in warehouse_qs]

    # ---------------- INVENTORY GROWTH ----------------
    growth_qs = (
        qs.annotate(month=TruncMonth("date_added"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    growth_labels, growth_data = [], []
    running_total = 0
    for row in growth_qs:
        running_total += row["count"]
        growth_labels.append(row["month"].strftime("%b %Y"))
        growth_data.append(running_total)

    return render(
        request,
        "inventory/inventory.html",
        {
            "page_obj": page_obj,
            "search_query": search_query,
            "total_items": total_items,
            "new_items_30": new_items_30,
            "warehouse_labels": warehouse_labels,
            "warehouse_data": warehouse_data,
            "growth_labels": growth_labels,
            "growth_data": growth_data,
            "current_sort": sort,
            "current_dir": direction,
            "inventory_fields": inventory_fields,
            "next_dirs": next_dirs,
            "is_superadmin": is_superadmin,
        },
    )


@login_required
def inventory_detail(request, pk):
    item = get_object_or_404(
        InventoryItem.objects.select_related("current_warehouse"),
        pk=pk
    )

    movements = item.movements.select_related(
        "from_warehouse", "to_warehouse"
    )

    paginator = Paginator(movements, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "inventory/inventory_detail.html",
        {
            "item": item,
            "page_obj": page_obj,
        },
    )

# =========================
# MOVE INVENTORY ITEM
# =========================

@login_required
def move_item(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)

    if request.method == "POST":
        form = InventoryMoveForm(request.POST)
        if form.is_valid():
            movement = form.save(commit=False)
            movement.item = item
            movement.from_warehouse = item.current_warehouse
            movement.moved_by = request.user
            movement.save()

            # update item warehouse
            item.current_warehouse = movement.to_warehouse
            item.save()

            messages.success(request, "Item moved successfully.")
            return redirect("inventory_page")
    else:
        form = InventoryMoveForm()

    return render(request, "inventory/move_item.html", {
        "item": item,
        "form": form
    })
