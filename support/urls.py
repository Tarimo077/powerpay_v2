from django.urls import path
from . import views

app_name = "support"

urlpatterns = [
    path('create/', views.create_ticket, name='create_ticket'),
    path('my-tickets/', views.ticket_list, name='support_ticket_list'),
    path('admin/', views.admin_ticket_list, name='admin_ticket_list'),
    path('admin/<int:ticket_id>/', views.admin_ticket_detail, name='admin_ticket_detail'),
    path("ticket/<int:ticket_id>/", views.ticket_detail, name="ticket_detail"),

]
