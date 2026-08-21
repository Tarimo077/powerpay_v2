from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Invoice, InvoiceItem, Receipt, SaaSBillingRule
from .forms import (
    CustomInvoiceForm,
    CustomInvoiceItemFormSet,
    HardwareInvoiceForm,
    SaaSInvoiceForm,
    SaaSBillingRuleForm,
)
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
from core.form_actions import resolve_post_save_redirect


# ==========================================
# PLATFORM BILLING ACCESS
# (PowerPay internal billing team)
# Can create/edit/delete invoices
# ==========================================
def billing_manage_access(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or (
                getattr(user, "role", "") == "superadmin"
                and getattr(user, "organization_id", None) == 1
            )
        )
    )


# ==========================================
# CUSTOMER BILLING ACCESS
# Org admins/superadmins can view invoices
# for their own organization
# ==========================================
def billing_view_access(user):
    return bool(
        user
        and user.is_authenticated
        and (
            billing_manage_access(user)
            or getattr(user, "role", None) in ["superadmin", "admin"]
        )
    )


def can_access_invoice(user, invoice):
    if billing_manage_access(user):
        return True

    return bool(
        billing_view_access(user)
        and getattr(user, "organization_id", None)
        and invoice.organization_id == user.organization_id
    )


def can_access_receipt(user, receipt):
    invoice = getattr(receipt, "invoice", None)
    return bool(invoice and can_access_invoice(user, invoice))



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
@login_required
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
@login_required
def create_hardware(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    form = HardwareInvoiceForm(request.POST or None)
    form.fields["organization"].queryset = Organization.objects.all()

    if request.method == "POST" and form.is_valid():
        organization = form.cleaned_data["organization"]
        inventory_items = form.cleaned_data["inventory_items"]
        unit_price = form.cleaned_data["unit_price"]
        due_date = form.cleaned_data["due_date"]

        # --- NEW: TAX & UPFRONT ---
        hardware_tax = form.cleaned_data.get("hardware_tax_percent", 0) or 0
        hardware_upfront = form.cleaned_data.get("hardware_upfront_percent", 0) or 0

        invoice = create_hardware_invoice(
            request.user,
            organization,
            inventory_items,
            unit_price,
            due_date,
            custom_product=form.cleaned_data.get("custom_product"),
            custom_quantity=form.cleaned_data.get("custom_quantity") or 1,
            #hardware_tax=hardware_tax,
            #hardware_upfront=hardware_upfront
        )

        return resolve_post_save_redirect(
            request,
            invoice,
            default_url="billing:invoice_list",
            create_url="billing:invoice_create_hardware",
            label="Invoice",
        )


    return render(request, "billing/invoice_form.html", {"form": form, "invoice_type": "HARDWARE"})


# ==========================================
# CREATE SAAS INVOICE
# INTERNAL ONLY
# ==========================================
@login_required
def create_saas(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    form = SaaSInvoiceForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        org = form.cleaned_data["organization"]
        unit_price = form.cleaned_data["unit_price"]
        due_date = form.cleaned_data["due_date"]

        # --- NEW: TAX & ADVANCE PERIOD ---
        saas_tax = form.cleaned_data.get("saas_tax_percent", 0) or 0
        saas_period = form.cleaned_data.get("saas_advance_period", "as_is")
        saas_custom_days = form.cleaned_data.get("saas_custom_days", None)

        # calculate actual due_date for SaaS based on period
        if saas_period == "1_year":
            due_date = timezone.now().date() + timedelta(days=365)
        elif saas_period == "custom" and saas_custom_days:
            due_date = timezone.now().date() + timedelta(days=saas_custom_days)
        # else leave due_date as-is

        invoice = create_saas_invoice(
            org,
            unit_price,
            request.user,
            due_date=due_date,
            #saas_tax=saas_tax
        )

        return resolve_post_save_redirect(
            request,
            invoice,
            default_url="billing:invoice_list",
            create_url="billing:invoice_create_saas",
            label="Invoice",
        )


    return render(request, "billing/invoice_form.html", {
        "form": form,
        "invoice_type": "SAAS"
    })


@login_required
def create_custom_invoice(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    invoice = Invoice(created_by=request.user, invoice_type="CUSTOM")
    form = CustomInvoiceForm(request.POST or None, instance=invoice)
    formset = CustomInvoiceItemFormSet(request.POST or None, instance=invoice)

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            invoice = form.save(commit=False)
            invoice.created_by = request.user
            if not invoice.invoice_number:
                from .services import generate_invoice_number
                invoice.invoice_number = generate_invoice_number()
            invoice.save()
            formset.instance = invoice
            formset.save()
            recalculate(invoice, tax=form.cleaned_data["tax"])

        return resolve_post_save_redirect(
            request,
            invoice,
            default_url="billing:invoice_detail",
            default_kwargs={"pk": invoice.pk},
            create_url="billing:invoice_create_custom",
            label="Invoice",
        )

    return render(request, "billing/custom_invoice_form.html", {"form": form, "formset": formset})


# ==========================================
# INVOICE DETAIL
# Internal billing -> any invoice
# Customer users -> own org invoices only
# ==========================================
@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    if not can_access_invoice(request.user, invoice):
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
@login_required
def invoice_edit(request, pk):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    invoice = get_object_or_404(Invoice, pk=pk)

    form = CustomInvoiceForm(request.POST or None, instance=invoice)
    formset = CustomInvoiceItemFormSet(request.POST or None, instance=invoice)

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            invoice = form.save()
            formset.save()
            recalculate(invoice, tax=form.cleaned_data["tax"])

        return resolve_post_save_redirect(
            request,
            invoice,
            default_url="billing:invoice_detail",
            default_kwargs={"pk": invoice.pk},
            edit_url_name="billing:invoice_edit",
            label="Invoice",
        )


    return render(request, "billing/custom_invoice_form.html", {
        "form": form, "formset": formset, "invoice": invoice,
    })


# ==========================================
# DELETE INVOICE
# INTERNAL ONLY
# ==========================================
@login_required
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
@login_required
def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)

    if not can_access_invoice(request.user, invoice):
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
@login_required
def devices_by_org(request, org_id):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    devices = billing_org_devices(org_id).values("id", "deviceid")

    return JsonResponse(
        list(devices),
        safe=False
    )

@login_required
def send_invoice_view(request, pk):
    if not billing_view_access(request.user):
        return HttpResponseForbidden()

    invoice = get_object_or_404(Invoice, pk=pk)

    if not can_access_invoice(request.user, invoice):
        return HttpResponseForbidden()

    if send_invoice(invoice, request.user):
        invoice.status = "SENT"
        invoice.save()

    return redirect("billing:invoice_detail", pk=invoice.pk)

@login_required
def receipt_list(request):

    user = request.user

    if billing_manage_access(user):
        receipts = Receipt.objects.all()

    elif billing_view_access(user):
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

@login_required
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

@login_required
def receipt_detail(request, pk):

    receipt = get_object_or_404(
        Receipt.objects.select_related("invoice", "invoice__organization"),
        pk=pk
    )

    if not can_access_receipt(request.user, receipt):
        return HttpResponseForbidden()

    return render(
        request,
        "billing/receipt_detail.html",
        {
            "receipt": receipt
        }
    )

@login_required
def receipt_pdf(request, pk):

    receipt = get_object_or_404(
        Receipt.objects.select_related("invoice", "invoice__organization"),
        pk=pk
    )

    if not can_access_receipt(request.user, receipt):
        return HttpResponseForbidden()

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
@login_required
def saas_rule_list(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    rules = SaaSBillingRule.objects.select_related("organization", "created_by").all()

    return render(request, "billing/saas_rule_list.html", {"rules": rules})


@login_required
def saas_rule_create(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    form = SaaSBillingRuleForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        rule = form.save(commit=False)
        rule.created_by = request.user
        rule.save()
        messages.success(request, "SaaS billing rule created successfully.")
        return resolve_post_save_redirect(
            request,
            rule,
            default_url="billing:saas_rule_list",
            create_url="billing:saas_rule_create",
            edit_url_name="billing:saas_rule_edit",
            label="Billing rule",
        )

    return render(request, "billing/saas_rule_form.html", {"form": form, "title": "Create SaaS Billing Rule"})


@login_required
def saas_rule_edit(request, pk):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    rule = get_object_or_404(SaaSBillingRule, pk=pk)
    form = SaaSBillingRuleForm(request.POST or None, instance=rule)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "SaaS billing rule updated successfully.")
        return resolve_post_save_redirect(
            request,
            rule,
            default_url="billing:saas_rule_list",
            create_url="billing:saas_rule_create",
            edit_url_name="billing:saas_rule_edit",
            label="Billing rule",
        )


    return render(request, "billing/saas_rule_form.html", {"form": form, "title": "Edit SaaS Billing Rule", "rule": rule})


@login_required
def saas_rule_delete(request, pk):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    rule = get_object_or_404(SaaSBillingRule, pk=pk)

    if request.method == "POST":
        rule.delete()
        messages.success(request, "SaaS billing rule deleted successfully.")
        return redirect("billing:saas_rule_list")

    return redirect("billing:saas_rule_list")


@login_required
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


@login_required
def run_due_saas_rules_view(request):
    if not billing_manage_access(request.user):
        return HttpResponseForbidden()

    count = run_due_saas_billing_rules()
    messages.success(request, f"{count} due SaaS billing rule(s) processed.")
    return redirect("billing:saas_rule_list")
