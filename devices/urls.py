from django.urls import path
from . import views

urlpatterns = [
    path("", views.device_list, name="device_list"),
    path("change_status_partial/", views.change_device_status_partial, name="change_device_status_partial"),
    path("change_status/", views.change_device_status, name="change_device_status"),
    path("<str:deviceid>/", views.device_detail, name="device_detail"),
    
   
]
