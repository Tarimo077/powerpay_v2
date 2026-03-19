from celery import shared_task
from django.utils import timezone
from django.db.models import Sum
from sales.models import Sale
from transactions.models import Transaction
from devices.models import DeviceInfo
from .models import PayGoSettings
from .utils import get_payment_plan_details


@shared_task
def enforce_paygo():

    today = timezone.now().date()

    settings_qs = PayGoSettings.objects.filter(auto_disable=True)

    for setting in settings_qs:

        sale = setting.sale
        plan = get_payment_plan_details(sale.payment_plan)

        if not plan or not sale.release_date:
            continue

        serial_last4 = sale.product_serial_number[-4:]

        txns = Transaction.objects.filter(
            ref__endswith=serial_last4,
            org=sale.organization
        )

        total_paid = txns.aggregate(total=Sum("amount"))["total"] or 0

        weeks = max((today - sale.release_date).days // 7, 0)

        expected_paid = plan["deposit"] + (weeks * plan["weekly_payment"])
        expected_paid = min(expected_paid, plan["total_price"])

        device_qs = DeviceInfo.objects.filter(deviceid__endswith=serial_last4)

        if total_paid < expected_paid * 0.7:
            device_qs.update(active=False)
        else:
            device_qs.update(active=True)