from django.apps import AppConfig


class DispatchingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app.dispatching"
    label = "dispatching"
    verbose_name = "Dispatching"

    def ready(self) -> None:
        pass
