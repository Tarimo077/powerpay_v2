from .models import OrganizationAppAccess

def app_access(request):
    if not request.user.is_authenticated:
        return {}

    org = getattr(request.user, "organization", None)

    if not org:
        return {}

    allowed_apps = list(
        OrganizationAppAccess.objects.filter(
            organization=org
        ).values_list("app_name", flat=True)
    )

    return {
        "allowed_apps": allowed_apps
    }