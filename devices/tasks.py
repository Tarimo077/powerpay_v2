from celery import shared_task
from django.utils import timezone
from .models import DeviceCommandSchedule
from .services.device_api import call_change_status_api

@shared_task
def run_pending_device_schedules():
    """
    Checks all DeviceCommandSchedule objects that are pending and sends commands.
    """
    now = timezone.now()
    pending_schedules = DeviceCommandSchedule.objects.filter(
        executed=False,
        scheduled_time__lte=now
    )

    for schedule in pending_schedules:
        for device in schedule.devices.all():
            print(device)
            result = call_change_status_api(device.deviceid, schedule.action)
            if result["success"]:
                print(f"{schedule.action} sent to {device.deviceid}")
            else:
                print(f"Error sending to {device.name}: {result['error']}")
        schedule.executed = True
        schedule.save()