from django.apps import AppConfig
from .services.mqtt_client import start_mqtt


class DevicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'devices'

    def ready(self):
        start_mqtt()
