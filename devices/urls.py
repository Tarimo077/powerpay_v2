from django.urls import path
from . import views

app_name = "devices"

urlpatterns = [
    # Device list and details
    path("", views.device_list, name="device_list"),
    path("testing-batches/", views.testing_batch_list, name="testing_batch_list"),
    path("testing-batches/create/", views.testing_batch_create, name="testing_batch_create"),
    path("testing-batches/<int:pk>/", views.testing_batch_detail, name="testing_batch_detail"),
    path("testing-batches/<int:pk>/delete/", views.testing_batch_delete, name="testing_batch_delete"),
    path("testing-batches/<int:pk>/update-results/", views.testing_batch_update_results, name="testing_batch_update_results"),
    path("testing-batches/<int:pk>/dispatch/", views.testing_batch_dispatch, name="testing_batch_dispatch"),
    path("testing-batches/<int:pk>/dispatch-detail/", views.testing_batch_dispatch_detail, name="testing_batch_dispatch_detail"),
    path("change_status/", views.change_device_status, name="change_device_status"),
    path("change_status_partial/", views.change_device_status_partial, name="change_device_status_partial"),
    path("schedules/", views.DeviceScheduleListView.as_view(), name="device_schedule_list"),
    path("schedules/add/", views.DeviceScheduleCreateView.as_view(), name="device_schedule_add"),
    path("schedules/<int:pk>/edit/", views.DeviceScheduleUpdateView.as_view(), name="device_schedule_edit"),
    path("schedules/<int:pk>/delete/", views.DeviceScheduleDeleteView.as_view(), name="device_schedule_delete"),
    path("schedules/<int:pk>/trigger/", views.trigger_schedule, name="device_schedule_trigger"),
    path("create/", views.device_create, name="device_create"),
    path("bulk-create/", views.device_bulk_create, name="device_bulk_create"),
    path("bulk-action/", views.device_bulk_action, name="device_bulk_action"),
    path("<str:deviceid>/", views.device_detail, name="device_detail"),
    path("edit/<str:deviceid>/", views.device_edit, name="device_edit"),
    path("delete/<str:deviceid>/", views.device_delete, name="device_delete"),
    path("live/<str:deviceid>/", views.device_live_view, name="device_live"),
    path("sim/check/", views.trigger_sim_balance, name="sim_check"),
    path("sim/callback/", views.sim_balance_callback, name="sim_callback"),
    path("sim/result/", views.sim_balance_result, name="sim_result"),
]
