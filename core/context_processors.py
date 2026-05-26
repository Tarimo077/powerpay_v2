from notifications.models import Notification

def unread_notifications_count(request):
    if request.user.is_authenticated:
        return {'unread_notif_count': request.user.notifications.filter(is_read=False).count()}
    return {'unread_notif_count': 0}

def user_roles(request):
    user = request.user

    is_role_superadmin = (
        user.is_authenticated
        and getattr(user, "role", None) == "superadmin"
    )
    is_django_superuser = user.is_authenticated and user.is_superuser
    is_platform_admin = user.is_authenticated and (
        is_django_superuser
        or is_role_superadmin
        or getattr(user, "role", None) == "admin"
    )
    can_manage_billing = user.is_authenticated and (
        is_django_superuser
        or (is_role_superadmin and getattr(user, "organization_id", None) == 1)
    )
    can_manage_support = user.is_authenticated and (
        is_django_superuser
        or is_role_superadmin
        or getattr(user, "role", None) in ["admin", "support"]
        or user.is_staff
    )

    return {
        # Template-facing permission flags. `is_superuser` intentionally includes
        # both Django superusers and users with the platform superadmin role so
        # menus/buttons match backend access checks.
        "is_superuser": is_django_superuser or is_role_superadmin,
        "is_admin": is_platform_admin,
        "can_manage_billing": can_manage_billing,
        "can_manage_support": can_manage_support,
        "user_org": getattr(user, "organization", None),
    }
