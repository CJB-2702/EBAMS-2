"""ModificationApplicabilityValidator — runtime applicability gate (Checkpoint 3).

The final, always-on guarantee that a modification is only recorded on an asset its
applicability permits. Called by ModificationManager.add_actual_modification before
any event or row is written, so a refused application leaves zero side effects.

Builds the read struct from the modification's mode + allow-lists and delegates the
verdict to ApplicabilityPolicy — the matrix logic is never re-implemented here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.control_layer.configurations.applicability.applicability_policy import (
    ApplicabilityPolicy,
)
from app.assets.control_layer.configurations.applicability.applicability_struct import (
    ApplicabilityStruct,
)
from app.assets.models.configurations.modifications.applicability_mode import ApplicabilityMode

if TYPE_CHECKING:
    from app.assets.models import Asset, DefinedModification


class ModificationApplicabilityValidator:
    """Validates that a DefinedModification may be applied to an Asset."""

    @staticmethod
    def check(asset: "Asset", defined_modification: "DefinedModification") -> None:
        """Raise ValueError if the modification's applicability forbids this asset."""
        applicability = ApplicabilityStruct(
            mode=ApplicabilityMode(defined_modification.applicability_mode),
            class_ids=frozenset(
                defined_modification.class_allowlist.values_list(
                    "asset_class_id", flat=True
                )
            ),
            model_ids=frozenset(
                defined_modification.model_allowlist.values_list("model_id", flat=True)
            ),
        )
        if not ApplicabilityPolicy.is_allowed(
            applicability,
            asset_class_id=asset.asset_class_id,
            asset_model_id=asset.model_id,
        ):
            reason = ApplicabilityPolicy.explain(
                applicability,
                asset_class_id=asset.asset_class_id,
                asset_model_id=asset.model_id,
            )
            raise ValueError(
                f"Modification '{defined_modification.name}' cannot be applied to "
                f"asset '{asset.name}': {reason}."
            )
