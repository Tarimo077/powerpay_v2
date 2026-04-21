from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import DeviceInfo, TrackKwh

@receiver(post_save, sender=DeviceInfo)
def create_track_kwh(sender, instance, created, **kwargs):
    if created:
        TrackKwh.objects.get_or_create(
            deviceid=instance.deviceid,
            defaults={"lastkwh": 0}
        )