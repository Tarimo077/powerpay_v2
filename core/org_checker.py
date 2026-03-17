from organizations.models import Organization, OrganizationAccess

def get_accessible_organizations(user):
    user_org = user.organization

    # If org cannot view others → only itself
    if not user_org.can_view_other_orgs:
        return Organization.objects.filter(id=user_org.id)

    # Get allowed target orgs
    accessible_ids = OrganizationAccess.objects.filter(
        source_org=user_org
    ).values_list("target_org_id", flat=True)

    # Include own org
    return Organization.objects.filter(
        id__in=list(accessible_ids) + [user_org.id]
    )