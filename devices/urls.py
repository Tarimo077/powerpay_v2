from django.urls import path
from . import views

urlpatterns = [
    # Device list and details
    path("", views.device_list, name="device_list"),
    path("create/", views.device_create, name="device_create"),
    path("<str:deviceid>/", views.device_detail, name="device_detail"),
    path("change_status_partial/", views.change_device_status_partial, name="change_device_status_partial"),
    path("change_status/", views.change_device_status, name="change_device_status"),
    path("edit/<str:deviceid>/", views.device_edit, name="device_edit"),
    path("delete/<str:deviceid>/", views.device_delete, name="device_delete"),
]
