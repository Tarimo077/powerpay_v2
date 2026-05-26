from django.urls import path
from . import views


app_name = "inventory"

urlpatterns = [
    path("", views.inventory_page, name="inventory_page"),
    path("items/<int:pk>/", views.inventory_detail, name="inventory_detail"),
    
    path("items/add/", views.item_create, name="item_create"),
    path("items/bulk-add/", views.bulk_item_create, name="bulk_item_create"),
    path("items/<int:pk>/edit/", views.item_update, name="item_update"),
    path("items/<int:pk>/delete/", views.item_delete, name="item_delete"),

    # Move item
    path("items/<int:pk>/move/", views.move_item, name="move_item"),
    path("items/bulk-move/", views.bulk_move_items, name="bulk_move_items"),

    # Delivery notes
    path("delivery-notes/", views.delivery_note_list, name="delivery_note_list"),
    path("delivery-notes/<int:pk>/", views.delivery_note_detail, name="delivery_note_detail"),
    path("delivery-notes/<int:pk>/pdf/", views.delivery_note_pdf, name="delivery_note_pdf"),
    path("delivery-notes/<int:pk>/email/", views.delivery_note_email, name="delivery_note_email"),
    path("delivery-notes/receive/<uuid:token>/", views.delivery_note_receive, name="delivery_note_receive"),
    path("delivery-notes/received/<uuid:token>/", views.delivery_note_received, name="delivery_note_received"),

    path("warehouses/", views.warehouses_page, name="warehouses_page"),
    path("warehouses/add/", views.warehouse_create, name="warehouse_create"),
    path("warehouses/<int:pk>/edit/", views.warehouse_update, name="warehouse_update"),
    path("warehouses/<int:pk>/delete/", views.warehouse_delete, name="warehouse_delete"),

    
   
]
