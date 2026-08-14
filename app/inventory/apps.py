from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.inventory"
    label = "inventory"
    verbose_name = "Inventory"

    def ready(self) -> None:
        pass
