from django.apps import AppConfig


class PartsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.parts"
    label = "parts"
    verbose_name = "Parts"

    def ready(self) -> None:
        pass
