from django.apps import AppConfig


class ConfigurationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.configuration"
    label = "configuration"
    verbose_name = "Configuration Management"

    def ready(self) -> None:
        pass
