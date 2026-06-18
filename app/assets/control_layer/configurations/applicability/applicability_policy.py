"""ApplicabilityPolicy — the pure allow/deny decision (the matrix heart).

DB-free and entity-agnostic. Given an ApplicabilityStruct and a concrete asset's
(class_id, model_id), it returns the matrix-correct verdict. This is the **single**
place the four-mode logic lives — both the authoring Manager and the runtime
Validator route through it, so there is no duplicated mode branching anywhere else.

Implements ``modification_class_and_model_matrix_behaviors.md`` §2–§3.
"""

from __future__ import annotations

from app.assets.control_layer.configurations.applicability.applicability_struct import (
    ApplicabilityStruct,
)
from app.assets.models.configurations.modifications.applicability_mode import ApplicabilityMode


class ApplicabilityPolicy:
    """Pure decision: may an asset receive an item with this applicability?"""

    @staticmethod
    def is_allowed(
        applicability: ApplicabilityStruct,
        *,
        asset_class_id: int,
        asset_model_id: int,
    ) -> bool:
        """Return True iff the asset is permitted under the matrix.

        AND combine: the asset must satisfy every enforced check. A check that is
        not enforced in the current mode passes unconditionally.
        """
        if (
            applicability.class_enforced
            and asset_class_id not in applicability.class_ids
        ):
            return False
        if (
            applicability.model_enforced
            and asset_model_id not in applicability.model_ids
        ):
            return False
        return True

    @staticmethod
    def explain(
        applicability: ApplicabilityStruct,
        *,
        asset_class_id: int,
        asset_model_id: int,
    ) -> str | None:
        """Human-readable reason for a denial, or None if allowed.

        Centralizes denial wording so the Validators don't each invent their own.
        Reports the first failing check in matrix order (class, then model).
        """
        if (
            applicability.class_enforced
            and asset_class_id not in applicability.class_ids
        ):
            allowed = sorted(applicability.class_ids)
            return (
                f"asset class {asset_class_id} is not in the permitted class set "
                f"{allowed or '{}'}"
            )
        if (
            applicability.model_enforced
            and asset_model_id not in applicability.model_ids
        ):
            allowed = sorted(applicability.model_ids)
            return (
                f"asset model {asset_model_id} is not in the permitted model set "
                f"{allowed or '{}'}"
            )
        return None

    @staticmethod
    def from_unrestricted(mode: ApplicabilityMode) -> bool:
        """Convenience: True when the mode gates nothing (applies anywhere)."""
        return mode == ApplicabilityMode.UNRESTRICTED
