from django.apps import AppConfig


class DetailExtensionsConfig(AppConfig):
    name = "app.detail_extensions"
    label = "detail_extensions"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from app.detail_extensions.control_layer.guards.extension_registry_guard import (
            ExtensionRegistryValidator,
        )
        from app.detail_extensions.control_layer.detail_extension_creation_orchestrator import (
            DetailExtensionCreationOrchestrator,
        )

        ExtensionRegistryValidator.assert_registry_valid()
        # Listen for owner creation and provision extensions post-commit (P2).
        DetailExtensionCreationOrchestrator.connect()
