from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("devices/", include("devices.urls")),
    path("transactions/", include("transactions.urls")),
    path("customers/", include("customers.urls")),
    path("sales/", include("sales.urls")),
    path("inventory/", include("inventory.urls")),
    path("support/", include("support.urls")),
    path("organizations/", include("organizations.urls")),
    path("notifications/", include("notifications.urls")),
    path("api/", include("api.urls")),
    path("", include("core.urls")),
]
