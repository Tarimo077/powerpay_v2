from collections import Counter, defaultdict
from django.db.models import Sum, Avg
from sales.models import Sale
from devices.models import DeviceData
from core.tasks import devices_for_organizations
from transactions.models import Transaction
from core.org_checker import get_accessible_organizations


def customer_device_analytics(organization=None, is_superadmin=False, user=None):
    """
    Customer + Sale + Device + Payments analytics.
    Fully aligned with core access models & optimized query execution.
    """
    # ==========================================================
    # 1. ACCESSIBLE ORGANIZATIONS & SALES
    # ==========================================================
    sales = (
        Sale.objects
        .select_related("customer", "organization")
        .order_by("-registration_date")
    )

    if organization:
        sales = sales.filter(organization=organization)
        accessible_org_ids = [organization.id]
    elif is_superadmin:
        accessible_org_ids = list(
            Sale.objects.values_list("organization_id", flat=True).distinct()
        )
    elif user:
        # Fetch organizations accessible to the standard user
        user_orgs = get_accessible_organizations(user)
        sales = sales.filter(organization__in=user_orgs)
        accessible_org_ids = list(user_orgs.values_list("id", flat=True))
    else:
        accessible_org_ids = []

    sales = list(sales)
    

    # ==========================================================
    # 2. DEVICES (Support legacy + M2M via core.tasks helper)
    # ==========================================================
    devices = devices_for_organizations(accessible_org_ids)
    device_lookup = {d.deviceid: d for d in devices}
    device_ids = list(device_lookup.keys())

    # ==========================================================
    # 3. DEVICE ENERGY AGGREGATION
    # ==========================================================
    device_energy = {}
    if device_ids:
        energy = (
            DeviceData.objects
            .filter(deviceid__in=device_ids)
            .values("deviceid")
            .annotate(
                total_kwh=Sum("kwh"),
                average_kwh=Avg("kwh"),
            )
        )
        device_energy = {
            row["deviceid"]: {
                "total_kwh": round(row["total_kwh"] or 0, 2),
                "average_kwh": round(row["average_kwh"] or 0, 3),
            }
            for row in energy
        }

    # ==========================================================
    # 4. LOAD TRANSACTIONS
    # ==========================================================
    if is_superadmin and not organization:
        transactions = Transaction.objects.select_related("org").order_by("-time")
    elif accessible_org_ids:
        transactions = Transaction.objects.filter(
            org_id__in=accessible_org_ids
        ).select_related("org").order_by("-time")
    else:
        transactions = Transaction.objects.none()

    tx_lookup = defaultdict(list)
    for tx in transactions:
        if not tx.ref:
            continue
        # Standardize matching key string
        key = str(tx.ref).strip().upper()
        tx_lookup[key].append(tx)

    # ==========================================================
    # 5. BUILD ANALYTICS ROWS
    # ==========================================================
    analytics = []
    for sale in sales:
        customer = sale.customer
        serial = (sale.product_serial_number or "").strip()
        
        device = device_lookup.get(serial)
        stats = device_energy.get(serial, {"total_kwh": 0, "average_kwh": 0})

        # Match exact serial first, fallback to suffix-4 matching if needed
        payments = tx_lookup.get(serial.upper())
        if payments is None:
            serial_suffix = serial[-4:].upper() if len(serial) >= 4 else serial.upper()
            payments = [
                tx for key, tx_list in tx_lookup.items() 
                if key.endswith(serial_suffix) 
                for tx in tx_list
            ]

        total_paid = sum(float(t.amount) for t in payments)

        analytics.append({
            # CUSTOMER
            "customer_name": customer.name,
            "phone": customer.phone_number,
            "email": customer.email,
            "county": customer.county.upper() if customer.county else "",
            "sub_county": customer.sub_county,
            "location": customer.location,
            "gender": customer.gender,
            "household_type": customer.household_type,
            "household_size": customer.household_size,
            "preferred_language": customer.preferred_language,

            # SALE
            "sale": sale,
            "product": sale.product_name,
            "product_model": sale.product_model,
            "product_serial_number": sale.product_serial_number,
            "product_type": sale.product_type,
            "purchase_mode": sale.purchase_mode,
            "payment_plan": sale.payment_plan,
            "type_of_use": sale.type_of_use,
            "sales_rep": sale.sales_rep,
            "registration_date": sale.registration_date,
            "release_date": sale.release_date,
            "metered": sale.metered,

            # DEVICE
            "device_id": device.deviceid if device else None,
            "device_active": device.active if device else False,
            "msisdn": device.msisdn if device else None,

            # ENERGY
            "total_kwh": stats["total_kwh"],
            "average_kwh": stats["average_kwh"],

            # PAYMENTS
            "transactions": payments,
            "payment_count": len(payments),
            "total_paid": round(total_paid, 2),
        })

    # ==========================================================
    # 6. SUMMARY STATS
    # ==========================================================
    total_sales = len(analytics)
    linked_devices = sum(1 for row in analytics if row["device_id"])
    unlinked_devices = total_sales - linked_devices
    
    total_energy = sum(row["total_kwh"] for row in analytics)
    average_energy = (total_energy / total_sales) if total_sales else 0

    purchase_modes = Counter(row["purchase_mode"] for row in analytics)
    product_types = Counter(row["product_type"] for row in analytics)
    counties = Counter(row["county"] or "N/A" for row in analytics)
    sales_reps = Counter(
        (row["sales_rep"] or "").split()[0] if row["sales_rep"] else "N/A" 
        for row in analytics
    )

    total_payments = sum(row["payment_count"] for row in analytics)
    total_amount_paid = sum(row["total_paid"] for row in analytics)

    return {
        "rows": analytics,
        "summary": {
            "customers": total_sales,
            "linked_devices": linked_devices,
            "unlinked_devices": unlinked_devices,
            "total_energy": round(total_energy, 2),
            "average_energy": round(average_energy, 2),
            "payments": total_payments,
            "amount_paid": round(total_amount_paid, 2),
        },
        "purchase_modes": dict(purchase_modes),
        "product_types": dict(product_types),
        "counties": dict(counties),
        "sales_reps": dict(sales_reps),
    }