from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("devices/", include("devices.urls", namespace="devices")),
    path("transactions/", include("transactions.urls", namespace="transactions")),
    path("customers/", include("customers.urls", namespace="customers")),
    path("paygo/", include("paygo.urls", namespace="paygo")),
    path("sales/", include("sales.urls", namespace="sales")),
    path("inventory/", include("inventory.urls", namespace="inventory")),
    path("support/", include("support.urls", namespace="support")),
    path("organizations/", include("organizations.urls", namespace="organizations")),
    path("notifications/", include("notifications.urls", namespace="notifications")),
    path("api/", include("api.urls", namespace="api")),
    path("", include("core.urls", namespace="core")),
    
]
