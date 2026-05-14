from django.core.exceptions import ValidationError
from .models import Invoice, InvoiceItem, Receipt
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal
from datetime import timedelta
from devices.models import DeviceInfo


def generate_invoice_number():
    return f"PP-INV-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"


def devices_for_billing_org(org):
    return (
        DeviceInfo.objects
        .filter(Q(organization=org) | Q(organizations=org))
        .distinct()
    )


def recalculate(invoice):
    subtotal = sum(i.total_price for i in invoice.items.all())
    tax = subtotal * Decimal("0.16")

    invoice.subtotal = subtotal
    invoice.tax = tax
    invoice.total = subtotal + tax
    invoice.save()


def create_hardware_invoice(user, devices, unit_price, due_date):

    if not devices:
        raise ValidationError("No devices selected")

    orgs = set(d.organization_id for d in devices)
    if len(orgs) != 1:
        raise ValidationError("All devices must belong to the same organization")

    org = devices.first().organization

    invoice = Invoice.objects.create(
        invoice_number=generate_invoice_number(),
        organization=org,
        invoice_type="HARDWARE",
        due_date=due_date,
        created_by=user
    )

    for device in devices:
        InvoiceItem.objects.create(
            invoice=invoice,
            device=device,
            description=f"IoT Device: {device.deviceid}",
            quantity=1,
            unit_price=Decimal(unit_price)
        )

    recalculate(invoice)
    return invoice


def create_saas_invoice(org, unit_price, user, due_date=None, description="SaaS subscription"):

    count = devices_for_billing_org(org).count()

    invoice = Invoice.objects.create(
        invoice_number=generate_invoice_number(),
        organization=org,
        invoice_type="SAAS",
        due_date=due_date or (timezone.now().date() + timedelta(days=7)),
        created_by=user
    )

    InvoiceItem.objects.create(
        invoice=invoice,
        description=description,
        quantity=count,
        unit_price=Decimal(unit_price)
    )

    recalculate(invoice)
    return invoice


def create_receipt_from_transaction(invoice, transaction):
    receipt, created = Receipt.objects.get_or_create(
        invoice=invoice,
        transaction=transaction,
        defaults={
            "amount": transaction.amount,
            "reference": transaction.txn_id
        }
    )

    return receipt