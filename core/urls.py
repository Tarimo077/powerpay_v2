from django.urls import path
from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("export/", views.export_data_view, name="export_data"),
    path("export/count/", views.export_count_view, name="export_count"), 
    path("customer-sales/", views.customer_sales_import_page, name="customer_sales_import_page"),
    path("customer-sales/upload/", views.import_customers_sales, name="import_customers_sales"), 
]
