class PowerpayRouter:
    """
    Routes database operations for apps to the correct DB.
    """
    route_app_labels = {'accounts', 'notifications', 'support'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'default'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'default'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Relations within same DB allowed
        db_set = {'default', 'coords', 'mpesa'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.route_app_labels:
            return db == 'default'
        return None


class CoordsRouter:
    route_app_labels = {'devices', 'organizations', 'transactions', 'customers', 'sales', 'inventory'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'coords'
        return None

    def db_for_write(self, model, **hints):
        # Devices are read-only, never write
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations if either object comes from coords
        db_set = {'coords'}
        if obj1._state.db in db_set or obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Never migrate devices app
        if app_label in self.route_app_labels:
            return False
        return None


