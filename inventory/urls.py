from django.urls import path
from . import views


app_name = "inventory"

urlpatterns = [
    path("", views.inventory_page, name="inventory_page"),
    path("items/<int:pk>/", views.inventory_detail, name="inventory_detail"),
    
    path("items/add/", views.item_create, name="item_create"),
    path("items/<int:pk>/edit/", views.item_update, name="item_update"),
    path("items/<int:pk>/delete/", views.item_delete, name="item_delete"),

    # Move item
    path("items/<int:pk>/move/", views.move_item, name="move_item"),
    path("warehouses/", views.warehouses_page, name="warehouses_page"),
    path("warehouses/add/", views.warehouse_create, name="warehouse_create"),
    path("warehouses/<int:pk>/edit/", views.warehouse_update, name="warehouse_update"),
    path("warehouses/<int:pk>/delete/", views.warehouse_delete, name="warehouse_delete"),

    
   
]
