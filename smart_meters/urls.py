from django.urls import path
from . import views

app_name = "smart_meters"

urlpatterns = [
    path("", views.meter_list, name="meter_list"),
    path("<str:meter_number>/", views.meter_detail, name="meter_detail"),
]