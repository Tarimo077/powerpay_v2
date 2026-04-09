# organizations/utils.py

def get_allowed_apps(org):
    return list(
        org.app_access.values_list("app_name", flat=True)
    )