from rest_framework import routers
from django.urls import path, include
from api.views import (
    DeviceInfoViewSet,
    DeviceDataViewSet,
    CustomerViewSet,
    SaleViewSet,
    TransactionViewSet,
)
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

router = routers.DefaultRouter()
router.register("devices/info", DeviceInfoViewSet, basename="deviceinfo")
router.register("devices/data", DeviceDataViewSet, basename="devicedata")
router.register("customers", CustomerViewSet, basename="customers")
router.register("sales", SaleViewSet, basename="sales")
router.register("transactions", TransactionViewSet, basename="transactions")

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("", include(router.urls)),
]