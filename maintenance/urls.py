from django.urls import path

from . import views

app_name = "maintenance"

urlpatterns = [
    path("", views.maintenance_list, name="maintenance_list"),
    path("create/", views.maintenance_create, name="maintenance_create"),
    path("<int:pk>/", views.maintenance_detail, name="maintenance_detail"),
    path("<int:pk>/status/", views.maintenance_status_update, name="maintenance_status_update"),
    path("<int:pk>/comment/", views.maintenance_comment_add, name="maintenance_comment_add"),
    path("<int:pk>/photo/", views.maintenance_photo_add, name="maintenance_photo_add"),
    path("track/<uuid:token>/", views.maintenance_public, name="maintenance_public"),
]
