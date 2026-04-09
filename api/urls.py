from django.urls import path, include
from rest_framework import routers
from api.views import (
    DeviceInfoViewSet, DeviceDataViewSet, CustomerViewSet, 
    SaleViewSet, TransactionViewSet
)
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

router = routers.DefaultRouter()
router.register("customers", CustomerViewSet, basename="customers")
router.register("sales", SaleViewSet, basename="sales")
router.register("transactions", TransactionViewSet, basename="transactions")

app_name = "api"

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # Devices Info: Only detail view
    
    path("devices/info/<str:deviceid>/", DeviceInfoViewSet.as_view({'get': 'retrieve'}), name="deviceinfo-detail"),

    # Devices Data: List (all aggregated) and Detail (one aggregated)
    path("devices/data/", DeviceDataViewSet.as_view({'get': 'list'}), name="devicedata-list"),
    path("devices/data/<str:deviceid>/", DeviceDataViewSet.as_view({'get': 'retrieve'}), name="devicedata-detail"),

    path("", include(router.urls)),
]