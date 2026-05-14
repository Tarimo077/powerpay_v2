from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import SaaSBillingRule
from .services import create_saas_invoice
from .utils import send_invoice


@shared_task
def run_due_saas_billing_rules():
    now = timezone.now()
    rules = SaaSBillingRule.objects.select_related("organization", "created_by").filter(
        active=True,
        next_run_at__lte=now,
    )

    created = 0

    for rule in rules:
        invoice = create_saas_invoice(
            org=rule.organization,
            unit_price=rule.rate_per_device,
            user=rule.created_by,
            due_date=now.date() + timedelta(days=rule.due_days),
            description=f"SaaS subscription - {rule.name}",
        )

        if rule.auto_send_email:
            if send_invoice(invoice, rule.created_by):
                invoice.status = "SENT"
                invoice.save(update_fields=["status"])

        rule.next_run_at = now + timedelta(days=rule.interval_days)
        rule.save(update_fields=["next_run_at", "updated_at"])
        created += 1

    return created
