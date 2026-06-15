from clickhouse_backend.models import ClickhouseModel


def get_subclasses(class_):
    classes = class_.__subclasses__()

    index = 0
    while index < len(classes):
        classes.extend(classes[index].__subclasses__())
        index += 1

    return list(set(classes))


class ClickHouseRouter:
    def __init__(self):
        self.route_model_names = set()
        for model in get_subclasses(ClickhouseModel):
            if model._meta.abstract:
                continue
            self.route_model_names.add(model._meta.label_lower)

    def db_for_read(self, model, **hints):
        if (model._meta.label_lower in self.route_model_names
                or hints.get("clickhouse")):
            return "clickhouse"
        return None

    def db_for_write(self, model, **hints):
        if (model._meta.label_lower in self.route_model_names
                or hints.get("clickhouse")):
            return "clickhouse"
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if (f"{app_label}.{model_name}" in self.route_model_names
                or hints.get("clickhouse")):
            return db == "clickhouse"
        elif db == "clickhouse":
            return False
        return None
    
    
class CoordsRouter:
    """
    Directs all operations to the 'coords' database.
    Manages migrations for specific apps while protecting existing tables.
    """

    # Apps we want to fully manage (create/update tables) in Postgres
    migrate_apps = {
        "accounts",
        "notifications",
        "support",
        "auth",           # Required for User/Group models
        "contenttypes",   # Required for Permissions
        "sessions",       # Required for Login sessions
        "admin",          # Required for Django Admin
        "django_celery_beat",
        "paygo",
        "billing",
    }

    # Apps that already exist in Postgres (We use them, but don't migrate them)
    external_no_migrate_apps = {
        "organizations",
        "transactions",
        "customers",
        "sales",
        "inventory",
    }

    def db_for_read(self, model, **hints):
        """All reads go to coords."""
        return "coords"

    def db_for_write(self, model, **hints):
        """All writes go to coords."""
        return "coords"

    def allow_relation(self, obj1, obj2, **hints):
        """Allow all relations since everything is now in one DB (coords)."""
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Controls table creation. 
        Only runs if the target database is 'coords'.
        """
        if db != "coords":
            return False

        # 1. Allow full migration for project & system apps
        if app_label in self.migrate_apps:
            return True

        # 2. Selective migration for 'devices' app
        if app_label == "devices":
            if model_name and model_name.lower() == "devicecommandschedule":
                return True
            return False


        # 3. Explicitly block existing data tables
        if app_label in self.external_no_migrate_apps:
            return False

        # Default: Don't migrate anything else
        return False
    
class SmartMeterRouter:
    """
    Routes smart_meters app to the smart meters database.
    """
    route_app_labels = {"smart_meters"}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return "smart_meters"
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return "smart_meters"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if (
            obj1._meta.app_label in self.route_app_labels or
            obj2._meta.app_label in self.route_app_labels
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.route_app_labels:
            return db == "smart_meters"
        return None