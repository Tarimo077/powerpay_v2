
from django.urls import path
from .views import paygo_sales_view, toggle_auto_paygo

urlpatterns = [
    path("", paygo_sales_view, name="paygo_sales"),
    path("toggle/<int:sale_id>/", toggle_auto_paygo, name="toggle_auto_paygo"),
]