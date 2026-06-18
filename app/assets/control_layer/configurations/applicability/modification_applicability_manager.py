"""ModificationApplicabilityManager — author one modification's applicability.

Checkpoint 1 (author-time integrity) of the applicability chain. Owns the mode and
the two allow-lists of a single DefinedModification, enforcing the matrix's authoring
invariants:

  - MODEL_SET keeps the class set system-derived (no hand-authoring; re-derived on
    every model change).
  - STRICT rejects a "dead model" whose parent class is absent from the class list.
  - Mode transitions normalize the lists so the stored rows always match the new mode.

The pure derivation is delegated to ApplicabilitySyncHandler; the allow/deny matrix
to ApplicabilityPolicy (via the read struct). This manager only persists rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.configurations.applicability.applicability_struct import (
    ApplicabilityStruct,
)
from app.assets.control_layer.configurations.applicability.applicability_sync_handler import (
    ApplicabilitySyncHandler,
)
from app.assets.models.configurations import (
    ApplicabilityMode,
    ModificationAssetClass,
    ModificationModel,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import AssetClass, AssetModel, DefinedModification


class ModificationApplicabilityManager:
    """Manages a DefinedModification's mode and class/model allow-lists."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor
        self._sync = ApplicabilitySyncHandler(actor)

    # ── Read ─────────────────────────────────────────────────────────────────

    def struct(self, defined_mod: "DefinedModification") -> ApplicabilityStruct:
        """Aggregate the modification's mode + allow-lists into a read struct."""
        return ApplicabilityStruct(
            mode=ApplicabilityMode(defined_mod.applicability_mode),
            class_ids=frozenset(self._class_ids(defined_mod)),
            model_ids=frozenset(self._model_ids(defined_mod)),
        )

    # ── Mode ─────────────────────────────────────────────────────────────────

    def set_mode(
        self, defined_mod: "DefinedModification", mode: ApplicabilityMode
    ) -> "DefinedModification":
        """Switch the mode and normalize the stored lists to match it.

        - → MODEL_SET: re-derive the class set from the current models.
        - → STRICT: re-validate every model against the class set; reject on any
          dead model (its parent class absent from the class list).
        - → CLASS_ONLY / UNRESTRICTED: leave rows intact (now suggestions).
        """
        mode = ApplicabilityMode(mode)
        with transaction.atomic():
            if mode == ApplicabilityMode.MODEL_SET:
                self._rederive_class_set(defined_mod)
            elif mode == ApplicabilityMode.STRICT:
                self._assert_no_dead_models(defined_mod)
            defined_mod.applicability_mode = mode
            defined_mod.updated_by = self.actor
            defined_mod.save(update_fields=["applicability_mode", "updated_by", "updated_at"])
        return defined_mod

    # ── Class allow-list ───────────────────────────────────────────────────────

    def add_class(
        self, defined_mod: "DefinedModification", asset_class: "AssetClass"
    ) -> ModificationAssetClass:
        self._reject_class_authoring(defined_mod)
        row, _ = ModificationAssetClass.objects.get_or_create(
            defined_modification=defined_mod,
            asset_class=asset_class,
            defaults={"created_by": self.actor, "updated_by": self.actor},
        )
        return row

    def remove_class(
        self, defined_mod: "DefinedModification", asset_class: "AssetClass"
    ) -> None:
        self._reject_class_authoring(defined_mod)
        ModificationAssetClass.objects.filter(
            defined_modification=defined_mod, asset_class=asset_class
        ).delete()

    # ── Model allow-list ───────────────────────────────────────────────────────

    def add_model(
        self, defined_mod: "DefinedModification", model: "AssetModel"
    ) -> ModificationModel:
        """Add a model. STRICT enforces the dead-model guard; MODEL_SET re-derives."""
        mode = ApplicabilityMode(defined_mod.applicability_mode)
        with transaction.atomic():
            if mode == ApplicabilityMode.STRICT:
                if model.asset_class_id not in set(self._class_ids(defined_mod)):
                    raise ValueError(
                        f"Cannot add model '{model}' to modification "
                        f"'{defined_mod.name}': its class {model.asset_class_id} is not "
                        f"in the STRICT class allow-list, so it could never be "
                        f"applied (dead model)."
                    )
            row, _ = ModificationModel.objects.get_or_create(
                defined_modification=defined_mod,
                model=model,
                defaults={"created_by": self.actor, "updated_by": self.actor},
            )
            if mode == ApplicabilityMode.MODEL_SET:
                self._rederive_class_set(defined_mod)
        return row

    def remove_model(
        self, defined_mod: "DefinedModification", model: "AssetModel"
    ) -> None:
        """Remove a model. MODEL_SET re-derives the class set afterward."""
        mode = ApplicabilityMode(defined_mod.applicability_mode)
        with transaction.atomic():
            ModificationModel.objects.filter(
                defined_modification=defined_mod, model=model
            ).delete()
            if mode == ApplicabilityMode.MODEL_SET:
                self._rederive_class_set(defined_mod)

    # ── Set-reconcile editors (dual-listbox save) ──────────────────────────────

    def set_classes(
        self, defined_mod: "DefinedModification", class_ids: list[int]
    ) -> None:
        """Reconcile the class allow-list to ``class_ids``.

        Skipped in MODEL_SET mode, where the class set is system-derived from the
        models and must not be hand-authored.
        """
        if ApplicabilityMode(defined_mod.applicability_mode) == ApplicabilityMode.MODEL_SET:
            return
        desired = set(class_ids)
        existing = set(self._class_ids(defined_mod))
        to_remove = existing - desired
        to_add = desired - existing
        with transaction.atomic():
            if to_remove:
                ModificationAssetClass.objects.filter(
                    defined_modification=defined_mod, asset_class_id__in=to_remove
                ).delete()
            for class_id in to_add:
                ModificationAssetClass.objects.create(
                    defined_modification=defined_mod,
                    asset_class_id=class_id,
                    created_by=self.actor,
                    updated_by=self.actor,
                )

    def set_models(
        self, defined_mod: "DefinedModification", model_ids: list[int]
    ) -> None:
        """Reconcile the model allow-list to ``model_ids``.

        Removes dropped models first, then adds new ones through ``add_model`` so
        the STRICT dead-model guard and MODEL_SET re-derivation still apply.
        """
        from app.assets.models import AssetModel

        desired = set(model_ids)
        existing = set(self._model_ids(defined_mod))
        to_remove = existing - desired
        to_add = desired - existing
        models = {m.id: m for m in AssetModel.objects.filter(id__in=to_remove | to_add)}
        for model_id in to_remove:
            self.remove_model(defined_mod, models[model_id])
        for model_id in to_add:
            self.add_model(defined_mod, models[model_id])

    # ── Internals ──────────────────────────────────────────────────────────────

    def _class_ids(self, defined_mod: "DefinedModification") -> list[int]:
        return list(
            defined_mod.class_allowlist.values_list("asset_class_id", flat=True)
        )

    def _model_ids(self, defined_mod: "DefinedModification") -> list[int]:
        return list(defined_mod.model_allowlist.values_list("model_id", flat=True))

    def _reject_class_authoring(self, defined_mod: "DefinedModification") -> None:
        if ApplicabilityMode(defined_mod.applicability_mode) == ApplicabilityMode.MODEL_SET:
            raise ValueError(
                f"Modification '{defined_mod.name}' is in MODEL_SET mode; its class "
                f"allow-list is system-derived from the model set and cannot be "
                f"authored directly."
            )

    def _assert_no_dead_models(self, defined_mod: "DefinedModification") -> None:
        class_ids = set(self._class_ids(defined_mod))
        dead = [
            model_id
            for model_id, class_id in defined_mod.model_allowlist.values_list(
                "model_id", "model__asset_class_id"
            )
            if class_id not in class_ids
        ]
        if dead:
            raise ValueError(
                f"Cannot switch modification '{defined_mod.name}' to STRICT: "
                f"models {sorted(dead)} have parent classes absent from the class "
                f"allow-list (dead models). Add the classes or drop the models first."
            )

    def _rederive_class_set(self, defined_mod: "DefinedModification") -> None:
        """Rewrite the class rows to the distinct parents of the current models."""
        derived = self._sync.sync_class_set(model_ids=self._model_ids(defined_mod))
        existing = set(self._class_ids(defined_mod))
        to_add = derived - existing
        to_remove = existing - derived
        if to_remove:
            ModificationAssetClass.objects.filter(
                defined_modification=defined_mod, asset_class_id__in=to_remove
            ).delete()
        for class_id in to_add:
            ModificationAssetClass.objects.create(
                defined_modification=defined_mod,
                asset_class_id=class_id,
                created_by=self.actor,
                updated_by=self.actor,
            )
