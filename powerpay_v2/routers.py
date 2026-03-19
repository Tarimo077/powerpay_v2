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