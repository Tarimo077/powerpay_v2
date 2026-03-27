from organizations.models import Organization
from .org_checker import get_accessible_organizations


def get_user_orgs(user):
    """
    Returns queryset of organizations the user can access
    """
    if user.is_superuser or getattr(user, "role", "") == "superadmin":
        return Organization.objects.all()
    return get_accessible_organizations(user)


def get_user_org_ids(user):
    """
    Returns list of accessible organization IDs
    """
    return list(get_user_orgs(user).values_list("id", flat=True))


def filter_by_user_orgs(queryset, user, org_field="organization_id"):
    """
    Filters any queryset by user's accessible organizations

    Example:
        filter_by_user_orgs(DeviceInfo.objects.all(), user)
        filter_by_user_orgs(Transaction.objects.all(), user, "org_id")
    """
    org_ids = get_user_org_ids(user)
    return queryset.filter(**{f"{org_field}__in": org_ids})