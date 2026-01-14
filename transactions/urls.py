from django.urls import path
from . import views

urlpatterns = [
    path('', views.transactions_page, name='transactions_page'),
]
