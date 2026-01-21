from django.urls import path
from . import views

urlpatterns = [
    path("", views.inventory_page, name="inventory_page"),
    path("<int:pk>/", views.inventory_detail, name="inventory_detail"),
    path("warehouses/", views.warehouses_page, name="warehouses_page"),

    
   
]
