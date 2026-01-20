from django.urls import path
from . import views

urlpatterns = [
    path("", views.customers_page, name="customers_page"),
    path("<int:pk>/", views.customer_detail, name="customer_detail"),
    
   
]
