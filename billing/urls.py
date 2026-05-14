from django.urls import path
from . import views

app_name = "billing"

urlpatterns = [
    path("invoices", views.invoice_list, name="invoice_list"),
    path("devices/by-org/<int:org_id>/", views.devices_by_org, name="devices_by_org"),
    path("invoices/create/hardware/", views.create_hardware, name="invoice_create_hardware"),
    path("invoices/create/saas/", views.create_saas, name="invoice_create_saas"),
    path("invoice/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoice/<int:pk>/edit/", views.invoice_edit, name="invoice_edit"),
    path("invoice/<int:pk>/delete/", views.invoice_delete, name="invoice_delete"),
    path("invoice/<int:pk>/send/", views.send_invoice_view,name="invoice_send"),
    path("receipts/", views.receipt_list, name="receipt_list"),
    path("receipts/sync/", views.sync_invoice_payments, name="sync_invoice_payments"),
    path("receipt/<int:pk>/", views.receipt_detail, name="receipt_detail"),
    path("receipt/<int:pk>/pdf/", views.receipt_pdf, name="receipt_pdf"),
    path("invoice/<int:pk>/pdf/", views.invoice_pdf, name="invoice_pdf"),

    path("saas-rules/", views.saas_rule_list, name="saas_rule_list"),
    path("saas-rules/create/", views.saas_rule_create, name="saas_rule_create"),
    path("saas-rules/<int:pk>/edit/", views.saas_rule_edit, name="saas_rule_edit"),
    path("saas-rules/<int:pk>/delete/", views.saas_rule_delete, name="saas_rule_delete"),
    path("saas-rules/<int:pk>/run-now/", views.saas_rule_run_now, name="saas_rule_run_now"),
    path("saas-rules/run-due/", views.run_due_saas_rules_view, name="saas_rule_run_due"),
]