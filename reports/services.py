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

from core.org_checker import get_accessible_organizations
from customers.models import Customer
from devices.models import DeviceInfo
from inventory.models import InventoryItem
from organizations.models import Organization
from sales.models import Sale
from transactions.models import Transaction

ALL_SECTIONS = ("customers", "sales", "inventory", "devices", "transactions")

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
# DATA
# ==========================================================
def build_report_context(user, start, end, sections=None, organization=None):
    sections = sections or {name: True for name in ALL_SECTIONS}
    org_ids = accessible_org_ids(user)

    if organization is not None:
        org_ids = [organization.id] if organization.id in org_ids else []

    empty = not org_ids

    # ---- CUSTOMERS ----
    customers = Customer.objects.none()
    if sections.get("customers") and not empty:
        customers = (
            Customer.objects
            .filter(organization_id__in=org_ids, date__gte=start, date__lte=end)
            .select_related("organization")
            .order_by("-date")
        )

    # ---- SALES ----
    sales = Sale.objects.none()
    if sections.get("sales") and not empty:
        sales = (
            Sale.objects
            .filter(
                organization_id__in=org_ids,
                registration_date__gte=start.date(),
                registration_date__lte=end.date(),
            )
            .select_related("customer", "organization")
            .order_by("-registration_date")
        )

    # ---- INVENTORY ----
    inventory = InventoryItem.objects.none()
    if sections.get("inventory") and not empty:
        inventory = (
            InventoryItem.objects
            .filter(
                current_warehouse__organization_id__in=org_ids,
                date_added__gte=start.date(),
                date_added__lte=end.date(),
            )
            .select_related("current_warehouse", "current_warehouse__organization")
            .order_by("-date_added")
        )

    # ---- DEVICES ----
    devices = DeviceInfo.objects.none()
    if sections.get("devices") and not empty:
        devices = (
            DeviceInfo.objects
            .filter(
                Q(organization_id__in=org_ids) | Q(organizations__id__in=org_ids),
                time__gte=start,
                time__lte=end,
            )
            .select_related("organization")
            .distinct()
            .order_by("-time")
        )

    # ---- TRANSACTIONS ----
    transactions = Transaction.objects.none()
    transactions_total = 0
    if sections.get("transactions") and not empty:
        transactions = (
            Transaction.objects
            .filter(org_id__in=org_ids, time__gte=start, time__lte=end)
            .select_related("org")
            .order_by("-time")
        )
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
        "customers": customers,
        "sales": sales,
        "inventory": inventory,
        "devices": devices,
        "transactions": transactions,
        "summary": {
            "customers": len(customers),
            "sales": len(sales),
            "inventory": len(inventory),
            "inventory_units": inventory_units,
            "devices": len(devices),
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
