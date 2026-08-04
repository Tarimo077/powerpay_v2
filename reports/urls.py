from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_center, name="report_center"),
    path("download/", views.report_download, name="report_download"),
    path("schedules/", views.schedule_list, name="schedule_list"),
    path("schedules/new/", views.schedule_create, name="schedule_create"),
    path("schedules/<int:pk>/edit/", views.schedule_edit, name="schedule_edit"),
    path("schedules/<int:pk>/delete/", views.schedule_delete, name="schedule_delete"),
    path("schedules/<int:pk>/toggle/", views.schedule_toggle, name="schedule_toggle"),
    path("schedules/<int:pk>/run/", views.schedule_run_now, name="schedule_run_now"),
    path("history/", views.run_history, name="run_history"),
]
