from django.urls import path
from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("export/", views.export_data_view, name="export_data"),
    path("export/count/", views.export_count_view, name="export_count"), 
    path("import/", views.import_center, name="import_center"),
    path("import-cs/upload/", views.import_customers_sales, name="import_customers_sales"),
    path("terms-of-service/", views.terms_of_service, name="terms"),
    path("import-tx/upload/", views.import_transactions, name="import_transactions"),
]
