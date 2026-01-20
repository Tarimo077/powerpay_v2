from django.urls import path
from . import views

urlpatterns = [
    path("", views.sales_page, name="sales_page"),
    path("<int:pk>/", views.sale_detail, name="sale_detail"),
    
   
]
