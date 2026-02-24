from django.urls import path
from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("export/", views.export_data_view, name="export_data"),
    path("export/count/", views.export_count_view, name="export_count"),  
]
