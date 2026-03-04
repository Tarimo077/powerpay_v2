from django.urls import path
from . import views

urlpatterns = [
    # Device list and details
    path("", views.device_list, name="device_list"),
    path("change_status/", views.change_device_status, name="change_device_status"),
    path("change_status_partial/", views.change_device_status_partial, name="change_device_status_partial"),
    path("schedules/", views.DeviceScheduleListView.as_view(), name="device_schedule_list"),
    path("schedules/add/", views.DeviceScheduleCreateView.as_view(), name="device_schedule_add"),
    path("schedules/<int:pk>/edit/", views.DeviceScheduleUpdateView.as_view(), name="device_schedule_edit"),
    path("schedules/<int:pk>/delete/", views.DeviceScheduleDeleteView.as_view(), name="device_schedule_delete"),
    path("schedules/<int:pk>/trigger/", views.trigger_schedule, name="device_schedule_trigger"),
    path("create/", views.device_create, name="device_create"),
    path("<str:deviceid>/", views.device_detail, name="device_detail"),
    path("edit/<str:deviceid>/", views.device_edit, name="device_edit"),
    path("delete/<str:deviceid>/", views.device_delete, name="device_delete"),
    path("live/<str:deviceid>/", views.device_live_view, name="device_live"),
]
