from django.db.models import Q
from organizations.models import Organization
from devices.models import DeviceInfo
from .org_checker import get_accessible_organizations


def is_org_superadmin(user):
    return user.is_superuser or getattr(user, "role", "") == "superadmin"


def get_user_orgs(user):
    """
    Returns queryset of organizations the user can access.
    """
    if is_org_superadmin(user):
        return Organization.objects.all()
    return get_accessible_organizations(user)


def get_user_org_ids(user):
    """
    Returns list of accessible organization IDs.
    """
    return list(get_user_orgs(user).values_list("id", flat=True))


def get_user_devices(user):
    """
    Returns devices visible to a user after the DeviceInfo multi-org change.

    A device is visible if either:
    - its legacy/main organization_id is accessible, or
    - its M2M organizations list contains an accessible organization.
    """
    if is_org_superadmin(user):
        return (
            DeviceInfo.objects
            .all()
            .select_related("organization")
            .prefetch_related("organizations")
            .distinct()
        )

    org_ids = get_user_org_ids(user)

    return (
        DeviceInfo.objects
        .filter(
            Q(organization_id__in=org_ids) |
            Q(organizations__id__in=org_ids)
        )
        .select_related("organization")
        .prefetch_related("organizations")
        .distinct()
    )


def filter_by_user_orgs(queryset, user, org_field="organization_id"):
    """
    Filters any queryset by user's accessible organizations.

    For DeviceInfo querysets, use get_user_devices() instead so both the
    legacy organization_id and the new M2M organizations field are respected.
    """
    if getattr(queryset, "model", None) is DeviceInfo:
        return get_user_devices(user)

    org_ids = get_user_org_ids(user)
    return queryset.filter(**{f"{org_field}__in": org_ids})
