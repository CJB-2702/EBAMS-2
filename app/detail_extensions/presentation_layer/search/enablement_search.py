"""Read-only reads for the configuration UI.

No writes here — all reads used by the config landing and assign editor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.assets.models import AssetClass, AssetModel
from app.detail_extensions import registry
from app.detail_extensions.base.extension_descriptor import (
    DetailExtension,
    ExtensionTarget,
)
from app.detail_extensions.models.enablement import (
    DetailExtensionsByAssetClass,
    DetailExtensionsByModel,
    ModelDetailExtensionsByAssetClass,
)


@dataclass
class ExtensionAssignmentSummary:
    """Catalog row for the configuration landing: one extension + where it is enabled."""

    descriptor: type[DetailExtension]
    assigned_class_ids: set[int] = field(default_factory=set)
    assigned_model_ids: set[int] = field(default_factory=set)


def get_catalog() -> list[ExtensionAssignmentSummary]:
    """All registered extensions with their current enablement sets."""
    class_rows = {
        (r.asset_class_id, r.extension_key)
        for r in DetailExtensionsByAssetClass.objects.all()
    }
    model_rows = {
        (r.model_id, r.extension_key)
        for r in DetailExtensionsByModel.objects.all()
    }
    model_ext_class_rows = {
        (r.asset_class_id, r.extension_key)
        for r in ModelDetailExtensionsByAssetClass.objects.all()
    }

    summaries = []
    for descriptor in registry.EXTENSION_REGISTRY.values():
        summary = ExtensionAssignmentSummary(descriptor=descriptor)
        if descriptor.target is ExtensionTarget.ASSET:
            summary.assigned_class_ids = {
                class_id for class_id, key in class_rows if key == descriptor.key
            }
            summary.assigned_model_ids = {
                model_id for model_id, key in model_rows if key == descriptor.key
            }
        else:
            # MODEL-target: assigned via ModelDetailExtensionsByAssetClass
            summary.assigned_class_ids = {
                class_id for class_id, key in model_ext_class_rows if key == descriptor.key
            }
        summaries.append(summary)
    return summaries


@dataclass
class AssignEditorContext:
    """Context for the per-extension assignment editor page."""

    descriptor: type[DetailExtension]
    asset_classes: list  # AssetClass queryset/list
    asset_models: list   # AssetModel queryset/list (only for ASSET-target)
    enabled_class_ids: set[int]
    enabled_model_ids: set[int]


def get_assign_editor_context(extension_key: str) -> AssignEditorContext:
    """Load the data needed to render the assignment editor for one extension."""
    from app.detail_extensions.control_layer.guards.extension_registry_guard import (
        ExtensionRegistryValidator,
    )
    descriptor = ExtensionRegistryValidator.resolve(extension_key)

    asset_classes = list(AssetClass.objects.filter(is_active=True).order_by("name"))

    if descriptor.target is ExtensionTarget.ASSET:
        enabled_class_ids = set(
            DetailExtensionsByAssetClass.objects.filter(
                extension_key=extension_key
            ).values_list("asset_class_id", flat=True)
        )
        enabled_model_ids = set(
            DetailExtensionsByModel.objects.filter(
                extension_key=extension_key
            ).values_list("model_id", flat=True)
        )
        asset_models = list(
            AssetModel.objects.select_related("asset_class").filter(
                is_active=True
            ).order_by("asset_class__name", "model_name")
        )
    else:
        # MODEL-target: only class-scope assignment
        enabled_class_ids = set(
            ModelDetailExtensionsByAssetClass.objects.filter(
                extension_key=extension_key
            ).values_list("asset_class_id", flat=True)
        )
        enabled_model_ids = set()
        asset_models = []

    return AssignEditorContext(
        descriptor=descriptor,
        asset_classes=asset_classes,
        asset_models=asset_models,
        enabled_class_ids=enabled_class_ids,
        enabled_model_ids=enabled_model_ids,
    )
