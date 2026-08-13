from organizations.models import Organization, OrganizationAccess


def get_accessible_organizations_for_org(user_org):
    """
    Organizations viewable from a given organization.

    Dashboard access only depends on the viewer's organization, so this is the
    canonical implementation and lets caches be keyed per org instead of per user.
    """
    if user_org is None:
        return Organization.objects.none()

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


def get_accessible_organizations(user):
    return get_accessible_organizations_for_org(user.organization)
