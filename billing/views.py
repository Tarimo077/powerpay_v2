from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from .models import Invoice, InvoiceItem, Receipt, SaaSBillingRule
from .forms import HardwareInvoiceForm, SaaSInvoiceForm, SaaSBillingRuleForm
from .services import (
    create_hardware_invoice,
    create_saas_invoice,
    recalculate,
    create_receipt_from_transaction,
    devices_for_billing_org
)
from .utils import generate_pdf, send_invoice, generate_receipt_pdf
from organizations.models import Organization
from devices.models import DeviceInfo
from transactions.models import Transaction
from .tasks import run_due_saas_billing_rules


# ==========================================
# PLATFORM BILLING ACCESS
# (PowerPay internal billing team)
# Can create/edit/delete invoices
# ==========================================
def billing_manage_access(user):
    return (
        user.is_authenticated and
        getattr(user, "role", "") == "superadmin" and
        getattr(user, "organization_id", None) == 1
    )


# ==========================================
# CUSTOMER BILLING ACCESS
# Org admins/superadmins can view invoices
# for their own organization
# ==========================================
def billing_view_access(user):
    return (
        user.is_authenticated and
        getattr(user, "role", None) in ["superadmin", "admin"]
    )



def billing_org_devices(org_id):
    return (
        DeviceInfo.objects
        .filter(Q(organization_id=org_id) | Q(organizations__id=org_id))
        .distinct()
    )


# ==========================================
# LIST INVOICES
# Internal billing sees all
# Customer org users see theirs only
# ==========================================
def invoice_list(request):
    user = request.user

    if billing_manage_access(user):
        invoices = Invoice.objects.all().order_by("-id")

    elif billing_view_access(user):
        invoices = Invoice.objects.filter(
            organization=user.organization
        ).order_by("-id")

    else:
        return HttpResponseForbidden()

    return render(
        request,
        "billing/invoice_list.html",
        {"invoices": invoices}
    )


# ==========================================
# CREATE HARDWARE INVOICE
# INTERNAL ONLY
# ==========================================
def create_hardware(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    form = HardwareInvoiceForm(request.POST or None)

    form.fields["organization"].queryset = Organization.objects.all()

    if request.method == "POST":
        org_id = request.POST.get("organization")

        if org_id:
            form.fields["devices"].queryset = billing_org_devices(org_id)

    if request.method == "POST" and form.is_valid():
        devices = form.cleaned_data["devices"]

        invoice = create_hardware_invoice(
            request.user,
            devices,
            form.cleaned_data["unit_price"],
            form.cleaned_data["due_date"]
        )

        return redirect("billing:invoice_list")

    return render(
        request,
        "billing/invoice_form.html",
        {"form": form}
    )


# ==========================================
# CREATE SAAS INVOICE
# INTERNAL ONLY
# ==========================================
def create_saas(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    form = SaaSInvoiceForm(request.POST or None)

    if request.method == "POST":
        org_id = request.POST.get("organization")

        if org_id:
            form.fields["devices"].queryset = billing_org_devices(org_id)

    if request.method == "POST" and form.is_valid():
        org = form.cleaned_data["organization"]

        invoice = create_saas_invoice(
            org,
            form.cleaned_data["unit_price"],
            request.user,
            due_date=form.cleaned_data["due_date"],
        )

        return redirect("billing:invoice_list")

    return render(request, "billing/invoice_form.html", {
        "form": form,
        "invoice_type": "SAAS"
    })


# ==========================================
# INVOICE DETAIL
# Internal billing -> any invoice
# Customer users -> own org invoices only
# ==========================================
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    if billing_manage_access(request.user):
        pass

    elif billing_view_access(request.user):
        if invoice.organization != request.user.organization:
            return HttpResponseForbidden()

    else:
        return HttpResponseForbidden()

    return render(
        request,
        "billing/invoice_detail.html",
        {"invoice": invoice}
    )


# ==========================================
# EDIT INVOICE
# INTERNAL ONLY
# ==========================================
def invoice_edit(request, pk):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    invoice = get_object_or_404(Invoice, pk=pk)

    org_id = (
        request.POST.get("organization")
        or invoice.organization.id
    )

    selected_devices = invoice.items.exclude(
        device__isnull=True
    ).values_list("device_id", flat=True)

    initial_data = {
        "organization": invoice.organization,
        "unit_price": (
            invoice.items.first().unit_price
            if invoice.items.exists()
            else 0
        ),
        "due_date": invoice.due_date,
        "devices": selected_devices,
    }

    # HARDWARE INVOICE
    if invoice.invoice_type == "HARDWARE":

        form = HardwareInvoiceForm(
            request.POST or None,
            initial=initial_data
        )

        # Dynamic queryset (important for validation)
        form.fields["devices"].queryset = billing_org_devices(org_id)

    # SAAS INVOICE
    else:

        form = SaaSInvoiceForm(
            request.POST or None,
            initial=initial_data
        )

        # IMPORTANT:
        # Set queryset so selected hidden devices validate
        form.fields["devices"].queryset = billing_org_devices(org_id)

    if request.method == "POST" and form.is_valid():

        invoice.organization = form.cleaned_data["organization"]
        invoice.due_date = form.cleaned_data["due_date"]
        invoice.save()

        # HARDWARE → recreate selected items
        if invoice.invoice_type == "HARDWARE":

            devices = form.cleaned_data["devices"]
            unit_price = form.cleaned_data["unit_price"]

            invoice.items.all().delete()

            for device in devices:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    device=device,
                    description=f"IoT Device: {device.deviceid}",
                    quantity=1,
                    unit_price=unit_price
                )

        # SAAS → update pricing + quantity only
        elif invoice.invoice_type == "SAAS":

            count = devices_for_billing_org(invoice.organization).count()

            item = invoice.items.first()

            if item:
                item.quantity = count
                item.unit_price = form.cleaned_data["unit_price"]
                item.description = "Monthly SaaS subscription"
                item.save()

        # Recalculate totals
        recalculate(invoice)

        return redirect(
            "billing:invoice_detail",
            pk=invoice.pk
        )

    return render(
        request,
        "billing/invoice_form.html",
        {
            "form": form,
            "invoice": invoice,
            "invoice_type": invoice.invoice_type,  # needed by template JS
        }
    )


# ==========================================
# DELETE INVOICE
# INTERNAL ONLY
# ==========================================
def invoice_delete(request, pk):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    invoice = get_object_or_404(Invoice, pk=pk)
    invoice.delete()

    return redirect("billing:invoice_list")


# ==========================================
# PDF VIEW / DOWNLOAD
# Internal billing -> any invoice
# Customer users -> own org invoices only
# ==========================================
def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    if billing_manage_access(request.user):
        pass

    elif billing_view_access(request.user):
        if invoice.organization != request.user.organization:
            return HttpResponseForbidden()

    else:
        return HttpResponseForbidden()

    pdf = generate_pdf(invoice)

    response = HttpResponse(
        pdf,
        content_type="application/pdf"
    )

    response["Content-Disposition"] = (
        f'inline; filename="{invoice.invoice_number}.pdf"'
    )

    return response


# ==========================================
# AJAX DEVICES BY ORG
# INTERNAL ONLY
# ==========================================
def devices_by_org(request, org_id):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    devices = billing_org_devices(org_id).values("id", "deviceid")

    return JsonResponse(
        list(devices),
        safe=False
    )

def send_invoice_view(request, pk):
    if not billing_view_access(request.user):
        return HttpResponseForbidden()

    invoice = get_object_or_404(Invoice, pk=pk)

    if send_invoice(invoice, request.user):
        invoice.status = "SENT"
        invoice.save()

    return redirect("billing:invoice_detail", pk=invoice.pk)

def receipt_list(request):

    user = request.user

    if user.role in ["superadmin"]:
        receipts = Receipt.objects.all()

    elif user.role in ["admin"]:
        receipts = Receipt.objects.filter(
            invoice__organization=user.organization
        )

    else:
        return HttpResponseForbidden()

    receipts = receipts.order_by("-created_at")

    return render(
        request,
        "billing/receipt_list.html",
        {
            "receipts": receipts
        }
    )

def sync_invoice_payments(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    invoices = Invoice.objects.filter(
        status="SENT"
    )

    for invoice in invoices:
        transactions = Transaction.objects.filter(
            ref=invoice.invoice_number
        )

        for txn in transactions:
            create_receipt_from_transaction(
                invoice,
                txn
            )

        if transactions.exists():
            invoice.status = "PAID"
            invoice.save()

    return redirect("billing:receipt_list")

def receipt_detail(request, pk):

    receipt = get_object_or_404(
        Receipt,
        pk=pk
    )

    user = request.user

    if (
        not user.is_superuser
        and user.role in ["superadmin", "admin"]
        and receipt.invoice.organization != user.organization
    ):
        return HttpResponseForbidden()

    return render(
        request,
        "billing/receipt_detail.html",
        {
            "receipt": receipt
        }
    )

def receipt_pdf(request, pk):

    receipt = get_object_or_404(
        Receipt,
        pk=pk
    )

    pdf = generate_receipt_pdf(receipt)

    response = HttpResponse(
        pdf,
        content_type="application/pdf"
    )

    response["Content-Disposition"] = (
        f'inline; filename="receipt-{receipt.id}.pdf"'
    )

    return response

# ==========================================
# SAAS BILLING RULES
# INTERNAL ONLY
# ==========================================
def saas_rule_list(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    rules = SaaSBillingRule.objects.select_related("organization", "created_by").all()

    return render(request, "billing/saas_rule_list.html", {"rules": rules})


def saas_rule_create(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    form = SaaSBillingRuleForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        rule = form.save(commit=False)
        rule.created_by = request.user
        rule.save()
        messages.success(request, "SaaS billing rule created successfully.")
        return redirect("billing:saas_rule_list")

    return render(request, "billing/saas_rule_form.html", {"form": form, "title": "Create SaaS Billing Rule"})


def saas_rule_edit(request, pk):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    rule = get_object_or_404(SaaSBillingRule, pk=pk)
    form = SaaSBillingRuleForm(request.POST or None, instance=rule)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "SaaS billing rule updated successfully.")
        return redirect("billing:saas_rule_list")

    return render(request, "billing/saas_rule_form.html", {"form": form, "title": "Edit SaaS Billing Rule", "rule": rule})


def saas_rule_delete(request, pk):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    rule = get_object_or_404(SaaSBillingRule, pk=pk)

    if request.method == "POST":
        rule.delete()
        messages.success(request, "SaaS billing rule deleted successfully.")
        return redirect("billing:saas_rule_list")

    return redirect("billing:saas_rule_list")


def saas_rule_run_now(request, pk):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    rule = get_object_or_404(SaaSBillingRule, pk=pk)
    invoice = create_saas_invoice(
        org=rule.organization,
        unit_price=rule.rate_per_device,
        user=request.user,
        due_date=timezone.now().date() + timedelta(days=rule.due_days),
        description=f"SaaS subscription - {rule.name}",
    )

    if rule.auto_send_email:
        if send_invoice(invoice, request.user):
            invoice.status = "SENT"
            invoice.save(update_fields=["status"])

    messages.success(request, f"Invoice {invoice.invoice_number} generated from {rule.name}.")
    return redirect("billing:invoice_detail", pk=invoice.pk)


def run_due_saas_rules_view(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    count = run_due_saas_billing_rules()
    messages.success(request, f"{count} due SaaS billing rule(s) processed.")
    return redirect("billing:saas_rule_list")
