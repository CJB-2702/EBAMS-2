"""AssetModelFactory — stateless creation of an AssetModel root.

Validates the natural key, creates the model, links manufacturers (one primary),
and emits a "Model Created" lifecycle event. Wraps its work in one transaction.
Model-extension provisioning is no longer called here: creation emits
``asset_model_created`` as its last in-transaction statement and ``detail_extensions``
provisions post-commit by listening (the dependency was inverted in P2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.capabilities.capability_factory import CapabilityFactory
from app.assets.control_layer.guards.asset_model_uniqueness_guard import (
    AssetModelUniquenessValidator,
)
from app.assets.control_layer.narrators.asset_event_narrator import AssetEventNarrator
from app.assets.signals import asset_model_created
from app.assets.models import AssetModel, ModelManufacturer
from app.events.models import Event, EventStatus, EventType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AssetModelValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class AssetModelFactory:
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> AssetModel:
        errors = AssetModelUniquenessValidator.validate(
            model_name=data.get("model_name", ""),
            subtype_name=data.get("subtype_name"),
            revision=data.get("revision"),
            is_base_model=data.get("is_base_model", True),
            base_model_id=data.get("base_model_id"),
        )
        if errors:
            raise AssetModelValidationError(errors)

        with transaction.atomic():
            model = AssetModel.objects.create(
                model_name=data["model_name"],
                subtype_name=data.get("subtype_name") or None,
                revision=data.get("revision") or None,
                is_base_model=data.get("is_base_model", True),
                base_model_id=data.get("base_model_id"),
                asset_class_id=data["asset_class_id"],
                meter1_unit=data.get("meter1_unit") or None,
                meter2_unit=data.get("meter2_unit") or None,
                meter3_unit=data.get("meter3_unit") or None,
                meter4_unit=data.get("meter4_unit") or None,
                created_by=actor,
                updated_by=actor,
            )

            cls._link_manufacturers(
                model=model,
                manufacturer_ids=data.get("manufacturer_ids", []),
                primary_manufacturer_id=data.get("primary_manufacturer_id"),
                actor=actor,
            )

            # P4: copy class capability templates to new model.
            CapabilityFactory.copy_class_to_model(model=model, actor=actor)

            cls._emit_created_event(model=model, actor=actor)

            # Announce — last in-transaction statement. detail_extensions listens
            # and provisions post-commit; assets stays ignorant of extensions.
            asset_model_created.send(
                sender=AssetModel, model=model, actor_id=getattr(actor, "pk", None)
            )

        return model

    @staticmethod
    def _link_manufacturers(
        *, model, manufacturer_ids, primary_manufacturer_id, actor
    ) -> None:
        for manufacturer_id in manufacturer_ids:
            ModelManufacturer.objects.create(
                model=model,
                manufacturer_id=manufacturer_id,
                is_primary=(manufacturer_id == primary_manufacturer_id),
                created_by=actor,
                updated_by=actor,
            )

    @staticmethod
    def _emit_created_event(*, model, actor) -> None:
        title, description = AssetEventNarrator.model_created(model)
        # Model events are domain-scoped; use the model's first domain if present.
        domain_id = model.domains.values_list("id", flat=True).first()
        if domain_id is None:
            return  # no domain to scope the event to yet — skip cleanly.
        event = Event.objects.create(
            domain_id=domain_id,
            title=title,
            description=description,
            event_type=EventType.ASSET_MANAGEMENT,
            status=EventStatus.COMPLETE,
            created_by=actor,
            updated_by=actor,
        )
        # Model has no AssetEvent link (that join is asset-scoped); the event
        # stands alone for the model. Asset links are created in the orchestrator.
        del event
