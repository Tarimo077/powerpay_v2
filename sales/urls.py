from django.urls import path
from . import views

urlpatterns = [
    path("", views.sales_page, name="sales_page"),
    path("<int:pk>/", views.sale_detail, name="sale_detail"),
    path("new/", views.sale_create, name="sale_create"),
    path("<int:pk>/edit/", views.sale_update, name="sale_update"),
    path("<int:pk>/delete", views.sale_delete, name="sale_delete")
    
   
]
