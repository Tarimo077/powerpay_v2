from django.urls import path
from . import views

app_name = "paygo"

urlpatterns = [
    path("", views.paygo_sales_view, name="paygo_sales"),
    path("toggle/<int:sale_id>/", views.toggle_auto_paygo, name="toggle_auto_paygo"),
    path("stk/<int:sale_id>/", views.paygo_stk_push, name="paygo_stk_push"),
]