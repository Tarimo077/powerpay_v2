from django.shortcuts import redirect
from .models import OrganizationAppAccess
from django.contrib import messages

class AppAccessMiddleware:
    APP_MAP = {
        "/paygo": "paygo",
        "/inventory": "inventory",
        "/transactions": "transactions",
        "/customers": "customers",
        "/sales": "sales",
        "/organizations": "organizations",
        "/api": "api",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Superusers bypass everything
        if request.user.is_superuser:
            return self.get_response(request)

        path = request.path

        for prefix, app_name in self.APP_MAP.items():
            if path.startswith(prefix):

                has_access = OrganizationAppAccess.objects.filter(
                    organization=request.user.organization,
                    app_name=app_name
                ).exists()

                if not has_access:
                    messages.error(request, f"You do not have access to the {app_name} module.")
                    return redirect("core:index")  # or custom 403 page

        return self.get_response(request)