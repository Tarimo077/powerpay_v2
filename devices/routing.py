# devices/routing.py
from django.urls import re_path
from .consumers import MqttConsumer

websocket_urlpatterns = [
    # Removed the leading 'ws' if you find it still 404s, 
    # but usually, this matches the path AFTER the domain.
    re_path(r"^ws/mqtt/(?P<deviceid>[^/]+)/$", MqttConsumer.as_asgi()),
]