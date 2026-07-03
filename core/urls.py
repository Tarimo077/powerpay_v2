from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
    path("storyboard/", views.storyboard, name="storyboard"),
    path("export/", views.export_data_view, name="export_data"),
    path("export/count/", views.export_count_view, name="export_count"), 
    path("import/", views.import_center, name="import_center"),
    path("import-cs/upload/", views.import_customers_sales, name="import_customers_sales"),
    path("import-tx/upload/", views.import_transactions, name="import_transactions"),
    path('audit-logs/', views.audit_logs, name='audit_logs'),
]
