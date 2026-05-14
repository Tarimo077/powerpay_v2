from django.urls import path, include
from rest_framework import routers
from api.views import (
    APIInstructionView,
    DeviceInfoViewSet,
    DeviceStatusChangeView,
    DeviceActivateView,
    DeviceDeactivateView,
    DeviceDataViewSet,
    DeviceCommandScheduleViewSet,
    TrackKwhViewSet,
    CustomerViewSet,
    SaleViewSet,
    TransactionViewSet,
    DeviceWalletCheckView,
    DeviceWalletUpsertView,
    OrganizationViewSet,
    OrganizationAccessViewSet,
    OrganizationAppAccessViewSet,
    WarehouseViewSet,
    InventoryItemViewSet,
    InventoryMovementViewSet,
    InvoiceViewSet,
    InvoiceItemViewSet,
    ReceiptViewSet,
    SaaSBillingRuleViewSet,
    PayGoSettingsViewSet,
    TicketViewSet,
    TicketMessageViewSet,
)
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

router = routers.DefaultRouter()
router.register("customers", CustomerViewSet, basename="customers")
router.register("sales", SaleViewSet, basename="sales")
router.register("transactions", TransactionViewSet, basename="transactions")
router.register("device-schedules", DeviceCommandScheduleViewSet, basename="device-schedules")
router.register("track-kwh", TrackKwhViewSet, basename="track-kwh")
router.register("organizations", OrganizationViewSet, basename="organizations")
router.register("organization-access", OrganizationAccessViewSet, basename="organization-access")
router.register("organization-app-access", OrganizationAppAccessViewSet, basename="organization-app-access")
router.register("warehouses", WarehouseViewSet, basename="warehouses")
router.register("inventory-items", InventoryItemViewSet, basename="inventory-items")
router.register("inventory-movements", InventoryMovementViewSet, basename="inventory-movements")
router.register("invoices", InvoiceViewSet, basename="invoices")
router.register("invoice-items", InvoiceItemViewSet, basename="invoice-items")
router.register("receipts", ReceiptViewSet, basename="receipts")
router.register("saas-billing-rules", SaaSBillingRuleViewSet, basename="saas-billing-rules")
router.register("paygo-settings", PayGoSettingsViewSet, basename="paygo-settings")
router.register("tickets", TicketViewSet, basename="tickets")
router.register("ticket-messages", TicketMessageViewSet, basename="ticket-messages")

app_name = "api"


urlpatterns = [
    path("instructions/", APIInstructionView.as_view(), name="api-instructions"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="swagger-ui"),

    # Device info/detail only
    path("devices/info/<str:deviceid>/", DeviceInfoViewSet.as_view({"get": "retrieve"}), name="deviceinfo-detail"),

    # Device status write APIs
    path("devices/<str:deviceid>/status/", DeviceStatusChangeView.as_view(), name="device-status-change"),
    path("devices/<str:deviceid>/activate/", DeviceActivateView.as_view(), name="device-activate"),
    path("devices/<str:deviceid>/deactivate/", DeviceDeactivateView.as_view(), name="device-deactivate"),

    # Device energy data
    path("devices/data/", DeviceDataViewSet.as_view({"get": "list"}), name="devicedata-list"),
    path("devices/data/<str:deviceid>/", DeviceDataViewSet.as_view({"get": "retrieve"}), name="devicedata-detail"),

    # Device wallet linkages: superusers/superadmins and user id=17 only
    path("devices/wallet/link/", DeviceWalletUpsertView.as_view(), name="device-wallet-link"),
    path("devices/wallet/<str:deviceid>/", DeviceWalletCheckView.as_view(), name="device-wallet-check"),

    path("", include(router.urls)),
]
