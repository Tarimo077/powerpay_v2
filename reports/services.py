"""Report data building, PDF rendering and email delivery."""

import os
from datetime import datetime, time, timedelta
from io import BytesIO

from django.conf import settings
from django.db.models import Q, Sum
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from xhtml2pdf import pisa

from core.energy_tariffs import get_tariff_for_date
from core.org_checker import get_accessible_organizations
from core.org_utils import get_user_devices
from customers.models import Customer
from devices.models import DeviceData, DeviceInfo
from inventory.models import InventoryItem
from organizations.models import Organization
from sales.models import Sale
from transactions.models import Transaction

ALL_SECTIONS = ("customers", "sales", "inventory", "devices", "transactions")

# Same 20 minute inactivity gap used on the device detail page
COOKING_GAP_SECONDS = 20 * 60

PERIOD_CHOICES = [
    ("today", "Today"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
    ("month", "This month"),
    ("custom", "Custom range"),
]


# ==========================================================
# ACCESS
# ==========================================================
def user_is_superadmin(user):
    return bool(user and (user.is_superuser or getattr(user, "role", "") == "superadmin"))


def accessible_org_ids(user):
    if user_is_superadmin(user):
        return list(Organization.objects.values_list("id", flat=True))
    return list(get_accessible_organizations(user).values_list("id", flat=True))


# ==========================================================
# PERIOD RESOLUTION
# ==========================================================
def _as_aware(value, end_of_day=False):
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.combine(value, time.max if end_of_day else time.min)

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def resolve_period(preset, start=None, end=None):
    """Return (start_datetime, end_datetime) for a preset or custom range."""
    now = timezone.localtime(timezone.now())
    today = now.date()

    if preset == "custom" and start and end:
        return _as_aware(start), _as_aware(end, end_of_day=True)

    if preset == "today":
        return _as_aware(today), _as_aware(today, end_of_day=True)

    if preset == "30d":
        return _as_aware(today - timedelta(days=29)), _as_aware(today, end_of_day=True)

    if preset == "month":
        return _as_aware(today.replace(day=1)), _as_aware(today, end_of_day=True)

    # default: last 7 days
    return _as_aware(today - timedelta(days=6)), _as_aware(today, end_of_day=True)


# ==========================================================
# DEVICE USAGE
# ==========================================================
def build_device_usage(user, start, end, organization=None):
    """
    Per-device usage for devices that actually reported data in the period.

    Returns (rows, totals). Devices with no readings are excluded.
    Non-superadmins only see their accessible organizations' devices;
    superadmins see every device.
    """
    devices = get_user_devices(user)

    if organization is not None:
        devices = devices.filter(
            Q(organization_id=organization.id) | Q(organizations__id=organization.id)
        ).distinct()

    device_map = {d.deviceid: d for d in devices}
    if not device_map:
        return [], _empty_usage_totals()

    readings = (
        DeviceData.objects
        .filter(deviceid__in=list(device_map.keys()), time__gte=start, time__lte=end)
        .only("deviceid", "kwh", "time")
        .order_by("deviceid", "time")
    )

    grouped = {}
    for r in readings:
        grouped.setdefault(r.deviceid, []).append(r)

    rows = []
    for deviceid, device_readings in grouped.items():
        device = device_map.get(deviceid)

        # ---- ENERGY + COST (same per-reading loop as device_detail) ----
        total_kwh = 0.0
        total_cost = 0.0
        for r in device_readings:
            kwh = float(r.kwh or 0)
            rate = get_tariff_for_date(r.time.date())
            total_kwh += kwh
            total_cost += kwh * rate

        # ---- COOKING EVENTS (20 minute gap rule, as device_detail) ----
        events = []
        current_event = []
        prev_time = None

        for r in device_readings:
            if prev_time:
                gap = (r.time - prev_time).total_seconds()
                if gap > COOKING_GAP_SECONDS:
                    if current_event:
                        events.append(current_event)
                    current_event = []
            current_event.append(r)
            prev_time = r.time

        if current_event:
            events.append(current_event)

        cooking_minutes = 0.0
        for event in events:
            event_start = timezone.localtime(event[0].time)
            event_end = timezone.localtime(event[-1].time)
            cooking_minutes += (event_end - event_start).total_seconds() / 60

        rows.append({
            "deviceid": deviceid,
            "device": device,
            "organization": device.organization if device else None,
            "readings": len(device_readings),
            "kwh": total_kwh,
            "events": len(events),
            "cooking_minutes": cooking_minutes,
            "cooking_hours": cooking_minutes / 60,
            "cost": total_cost,
            "first_seen": timezone.localtime(device_readings[0].time),
            "last_seen": timezone.localtime(device_readings[-1].time),
        })

    rows.sort(key=lambda row: row["kwh"], reverse=True)

    total_minutes = sum(r["cooking_minutes"] for r in rows)

    totals = {
        "devices": len(rows),
        "kwh": sum(r["kwh"] for r in rows),
        "events": sum(r["events"] for r in rows),
        "cooking_minutes": total_minutes,
        "cooking_hours": total_minutes / 60,
        "cost": sum(r["cost"] for r in rows),
    }

    return rows, totals



def _empty_usage_totals():
    return {
        "devices": 0,
        "kwh": 0,
        "events": 0,
        "cooking_minutes": 0,
        "cooking_hours": 0,
        "cost": 0,
    }


# ==========================================================
# DATA
# ==========================================================
def build_report_context(user, start, end, sections=None, organization=None):
    sections = sections or {name: True for name in ALL_SECTIONS}
    is_superadmin = user_is_superadmin(user)
    org_ids = accessible_org_ids(user)

    if organization is not None:
        org_ids = [organization.id] if organization.id in org_ids else []

    # Superadmins see everything unless a specific organization is selected
    unrestricted = is_superadmin and organization is None
    empty = not unrestricted and not org_ids

    # ---- CUSTOMERS ----
    customers = Customer.objects.none()
    if sections.get("customers") and not empty:
        customers = (
            Customer.objects
            .filter(date__gte=start, date__lte=end)
            .select_related("organization")
            .order_by("-date")
        )
        if not unrestricted:
            customers = customers.filter(organization_id__in=org_ids)

    # ---- SALES ----
    sales = Sale.objects.none()
    if sections.get("sales") and not empty:
        sales = (
            Sale.objects
            .filter(
                registration_date__gte=start.date(),
                registration_date__lte=end.date(),
            )
            .select_related("customer", "organization")
            .order_by("-registration_date")
        )
        if not unrestricted:
            sales = sales.filter(organization_id__in=org_ids)

    # ---- INVENTORY ----
    inventory = InventoryItem.objects.none()
    if sections.get("inventory") and not empty:
        inventory = (
            InventoryItem.objects
            .filter(
                date_added__gte=start.date(),
                date_added__lte=end.date(),
            )
            .select_related("current_warehouse", "current_warehouse__organization")
            .order_by("-date_added")
        )
        if not unrestricted:
            inventory = inventory.filter(
                current_warehouse__organization_id__in=org_ids
            )

    # ---- DEVICES ----
    devices = DeviceInfo.objects.none()
    device_usage = []
    device_usage_totals = _empty_usage_totals()
    if sections.get("devices") and not empty:
        devices = (
            DeviceInfo.objects
            .filter(time__gte=start, time__lte=end)
            .select_related("organization")
            .distinct()
            .order_by("-time")
        )
        if not unrestricted:
            devices = devices.filter(
                Q(organization_id__in=org_ids) | Q(organizations__id__in=org_ids)
            )

        device_usage, device_usage_totals = build_device_usage(
            user, start, end, organization=organization
        )

    # ---- TRANSACTIONS ----
    transactions = Transaction.objects.none()
    transactions_total = 0
    if sections.get("transactions") and not empty:
        transactions = (
            Transaction.objects
            .filter(time__gte=start, time__lte=end)
            .select_related("org")
            .order_by("-time")
        )
        if not unrestricted:
            transactions = transactions.filter(org_id__in=org_ids)
        transactions_total = transactions.aggregate(total=Sum("amount"))["total"] or 0

    customers = list(customers)
    sales = list(sales)
    inventory = list(inventory)
    devices = list(devices)
    transactions = list(transactions)

    inventory_units = sum((item.quantity or 0) for item in inventory)

    return {
        "generated_at": timezone.localtime(timezone.now()),
        "generated_by": user,
        "period_start": start,
        "period_end": end,
        "days": max((end.date() - start.date()).days + 1, 1),
        "sections": sections,
        "organization": organization,
        "is_superadmin": is_superadmin,
        "customers": customers,
        "sales": sales,
        "inventory": inventory,
        "devices": devices,
        "device_usage": device_usage,
        "device_usage_totals": device_usage_totals,
        "transactions": transactions,
        "summary": {
            "customers": len(customers),
            "sales": len(sales),
            "inventory": len(inventory),
            "inventory_units": inventory_units,
            "devices": len(devices),
            "devices_used": device_usage_totals["devices"],
            "kwh": device_usage_totals["kwh"],
            "cooking_events": device_usage_totals["events"],
            "cooking_hours": device_usage_totals["cooking_hours"],
            "energy_cost": device_usage_totals["cost"],
            "transactions": len(transactions),
            "transactions_total": transactions_total,
        },
    }


# ==========================================================
# PDF
# ==========================================================
def render_report_pdf(context):
    html = render_to_string(
        "reports/report_pdf.html",
        {
            **context,
            "STATIC_ROOT": os.path.join(settings.BASE_DIR, "static"),
        },
    )

    result = BytesIO()
    pdf = pisa.CreatePDF(src=html, dest=result)

    if pdf.err:
        return None
    return result.getvalue()


def report_filename(context):
    return (
        "powerpay-report-"
        f"{context['period_start']:%Y%m%d}-{context['period_end']:%Y%m%d}.pdf"
    )


# ==========================================================
# EMAIL
# ==========================================================
def send_report_email(context, recipients, schedule=None):
    from billing.utils import send_pdf_email

    recipients = [r for r in recipients if r]
    if not recipients:
        return False

    pdf = render_report_pdf(context)

    html_body = render_to_string(
        "reports/emails/report_email.html",
        {**context, "schedule": schedule},
    )
    text_body = strip_tags(html_body)

    subject = (
        f"PowerPay Africa Report | "
        f"{context['period_start']:%d %b %Y} - {context['period_end']:%d %b %Y}"
    )

    send_pdf_email(
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        recipients=recipients,
        attachment_name=report_filename(context),
        pdf_bytes=pdf,
    )
    return True
