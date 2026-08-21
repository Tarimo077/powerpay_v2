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


def recalculate(invoice, tax=None):
    subtotal = sum(i.total_price for i in invoice.items.all())
    tax = subtotal * Decimal("0.16") if tax is None else Decimal(tax)

    invoice.subtotal = subtotal
    invoice.tax = tax
    invoice.total = subtotal + tax
    invoice.save()


def create_hardware_invoice(
    user, organization, inventory_items, unit_price, due_date,
    custom_product=None, custom_quantity=1,
):

    if not inventory_items and not custom_product:
        raise ValidationError("Select an inventory item or enter a custom product")

    invoice = Invoice.objects.create(
        invoice_number=generate_invoice_number(),
        organization=organization,
        invoice_type="HARDWARE",
        due_date=due_date,
        created_by=user
    )

    for item in inventory_items:
        InvoiceItem.objects.create(
            invoice=invoice,
            inventory_item=item,
            description=f"{item.name} ({item.serial_number})",
            quantity=1,
            unit_price=Decimal(unit_price)
        )

    if custom_product:
        InvoiceItem.objects.create(
            invoice=invoice,
            description=custom_product.strip(),
            quantity=custom_quantity or 1,
            unit_price=Decimal(unit_price),
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
