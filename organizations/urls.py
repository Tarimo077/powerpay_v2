from django.urls import path
from . import views

app_name = "organizations"

urlpatterns = [
    path("", views.organizations_page, name="organizations_page"),
    path("add/", views.organization_create, name="organization_create"),
    path("<int:pk>/edit/", views.organization_update, name="organization_update"),
    path("<int:pk>/delete/", views.organization_delete, name="organization_delete"),
]
