from django.apps import AppConfig


class DevicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'devices'

    def ready(self):
        from .services.mqtt_client import start_mqtt
        start_mqtt()
