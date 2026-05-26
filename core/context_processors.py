from notifications.models import Notification


def unread_notifications_count(request):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return {
            "unread_notif_count": 0,
        }

    try:
        count = user.notifications.filter(is_read=False).count()
    except AttributeError:
        count = Notification.objects.filter(
            user=user,
            is_read=False,
        ).count()

    return {
        "unread_notif_count": count,
    }


def user_roles(request):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return {
            "is_django_superuser": False,
            "is_role_superadmin": False,
            "is_role_admin": False,
            "is_role_support": False,
            "is_platform_admin": False,
            "is_admin": False,
            "is_superuser": False,
            "can_manage_organizations": False,
            "can_manage_devices": False,
            "can_manage_device_testing": False,
            "can_manage_inventory": False,
            "can_manage_warehouses": False,
            "can_manage_billing": False,
            "can_manage_support": False,
            "user_org": None,
            "user_role": None,
        }

    role = getattr(user, "role", None)

    is_django_superuser = bool(user.is_superuser)
    is_role_superadmin = role == "superadmin"
    is_role_admin = role == "admin"
    is_role_support = role == "support"

    is_platform_admin = (
        is_django_superuser
        or is_role_superadmin
        or is_role_admin
    )

    can_manage_organizations = (
        is_django_superuser
        or is_role_superadmin
    )

    can_manage_devices = is_platform_admin

    # Keep this strict if testing batches should only be visible to real Django superusers.
    can_manage_device_testing = is_django_superuser

    can_manage_inventory = is_platform_admin

    can_manage_warehouses = is_django_superuser

    can_manage_billing = (
        is_django_superuser
        or is_role_superadmin
        or is_role_admin
    )

    can_manage_support = (
        is_django_superuser
        or is_role_superadmin
        or is_role_admin
        or is_role_support
        or user.is_staff
    )

    return {
        # Exact Django permission flag.
        # Do not mix role-based superadmin into this.
        "is_django_superuser": is_django_superuser,

        # Role-specific flags.
        "is_role_superadmin": is_role_superadmin,
        "is_role_admin": is_role_admin,
        "is_role_support": is_role_support,

        # Platform-level aliases.
        "is_platform_admin": is_platform_admin,
        "is_admin": is_platform_admin,

        # Keep this backwards compatible, but make it mean true Django superuser only.
        "is_superuser": is_django_superuser,

        # Template-facing permission flags.
        "can_manage_organizations": can_manage_organizations,
        "can_manage_devices": can_manage_devices,
        "can_manage_device_testing": can_manage_device_testing,
        "can_manage_inventory": can_manage_inventory,
        "can_manage_warehouses": can_manage_warehouses,
        "can_manage_billing": can_manage_billing,
        "can_manage_support": can_manage_support,

        "user_org": getattr(user, "organization", None),
        "user_role": role,
    }