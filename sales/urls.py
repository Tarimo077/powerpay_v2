from django.urls import path
from . import views

app_name = "sales"

urlpatterns = [
    path("", views.sales_page, name="sales_page"),
    path("<int:pk>/", views.sale_detail, name="sale_detail"),
    path("new/", views.sale_create, name="sale_create"),
    path("<int:pk>/edit/", views.sale_update, name="sale_update"),
    path("<int:pk>/delete", views.sale_delete, name="sale_delete"),
    path("<int:pk>/receipt/pdf/", views.sale_receipt_pdf, name="sale_receipt_pdf"),
    path("<int:pk>/receipt/email/", views.sale_receipt_email, name="sale_receipt_email"),
    path("search/", views.customer_search, name="customer_search"),
    
   
]
