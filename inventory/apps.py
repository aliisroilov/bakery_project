from django.apps import AppConfig

class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'

    def ready(self):
        # Import signals so they are registered
        try:
            import inventory.signals  # noqa: F401
        except Exception:
            # avoid raising on import issues in migrations context
            pass
