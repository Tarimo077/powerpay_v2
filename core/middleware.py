from .org_checker import get_accessible_organizations
from organizations.models import Organization


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        user = request.user

        # Skip if not authenticated
        if not user.is_authenticated:
            return self.get_response(request)

        is_superadmin = user.is_superuser or getattr(user, "role", "") == "superadmin"

        # -------- GET FROM REQUEST OR SESSION --------
        org_param = request.GET.get("org", None)  # capture empty string
        session_org = request.session.get("org_id")

        selected_org = None
        org_id = None

        # -------- SUPERADMIN --------
        if is_superadmin:
            accessible_orgs = Organization.objects.all()

            if org_param is not None:  # handles ?org= or ?org=3
                if org_param == "":
                    # User selected "All Organizations"
                    org_id = None
                    selected_org = None
                else:
                    try:
                        org_id = int(org_param)
                        selected_org = accessible_orgs.filter(id=org_id).first()
                    except ValueError:
                        org_id = None
                        selected_org = None

            elif session_org:
                try:
                    org_id = int(session_org)
                    selected_org = accessible_orgs.filter(id=org_id).first()
                except ValueError:
                    org_id = None
                    selected_org = None

        # -------- NORMAL USER --------
        else:
            accessible_orgs = get_accessible_organizations(user)
            accessible_ids = list(accessible_orgs.values_list("id", flat=True))

            if org_param is not None:
                if org_param == "":
                    # All accessible organizations
                    org_id = None
                    selected_org = None
                else:
                    try:
                        org_id = int(org_param)
                        if org_id in accessible_ids:
                            selected_org = accessible_orgs.filter(id=org_id).first()
                        else:
                            org_id = None
                            selected_org = None
                    except ValueError:
                        org_id = None
                        selected_org = None

            elif session_org:
                try:
                    org_id = int(session_org)
                    if org_id in accessible_ids:
                        selected_org = accessible_orgs.filter(id=org_id).first()
                    else:
                        org_id = None
                        selected_org = None
                except ValueError:
                    org_id = None
                    selected_org = None

        # -------- SAVE TO SESSION --------
        if org_id:
            request.session["org_id"] = org_id
        else:
            request.session.pop("org_id", None)

        # -------- ATTACH CLEAN VALUES --------
        request.accessible_orgs = accessible_orgs
        request.selected_org = selected_org
        request.org_id = org_id  # 🔥 This is what your cache + views should use

        return self.get_response(request)