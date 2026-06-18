"""ApplicabilitySyncHandler — derive the class set from the model set (kit D3).

Single-task specialist. In MODEL_SET mode an item's class allow-list is not authored
— it must always equal the distinct parent classes of its model allow-list. This
handler computes that derived class id-set from a list of model ids; it does **not**
write entity-specific junction rows. The owning Manager (modification this phase,
template in Phase 2) persists the returned set into its own table, so the same pure
derivation serves both entities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from app.assets.models import AssetModel

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class ApplicabilitySyncHandler:
    """Computes the derived parent-class set for a set of asset models."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    def sync_class_set(self, *, model_ids: Iterable[int]) -> set[int]:
        """Return the distinct parent AssetClass ids for the given model ids.

        Empty input yields an empty set. The single mandatory
        ``AssetModel.asset_class`` FK is what makes this derivation total.
        """
        ids = list(model_ids)
        if not ids:
            return set()
        return set(
            AssetModel.objects.filter(id__in=ids).values_list(
                "asset_class_id", flat=True
            )
        )
