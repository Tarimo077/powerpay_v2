from django.urls import path
from . import views

app_name = "device_orders"

urlpatterns = [
    path("", views.order_list, name="order_list"),
    path("new/", views.order_create, name="order_create"),
    path("<int:pk>/", views.order_detail, name="order_detail"),
    path("<int:pk>/approve/", views.order_approve, name="order_approve"),
    path("<int:pk>/reject/", views.order_reject, name="order_reject"),
    path("<int:pk>/cancel/", views.order_cancel, name="order_cancel"),
    path("<int:pk>/fulfill/", views.order_fulfill, name="order_fulfill"),
]