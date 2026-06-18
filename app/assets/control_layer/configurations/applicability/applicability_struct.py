"""ApplicabilityStruct — immutable read model of one item's applicability.

Entity-agnostic: it carries the mode plus the two id-sets, not the owning row, so
it is built identically from a DefinedModification (Phase 1) or a
ConfigurationTemplate (Phase 2). The struct knows which lists *bind* in the current
mode versus which are mere suggestions; the allow/deny decision itself lives in
ApplicabilityPolicy. See the kit's matrix doc.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.assets.models.configurations.modifications.applicability_mode import ApplicabilityMode


@dataclass(frozen=True)
class ApplicabilityStruct:
    mode: ApplicabilityMode
    class_ids: frozenset[int]
    model_ids: frozenset[int]

    @property
    def class_enforced(self) -> bool:
        return self.mode in (ApplicabilityMode.STRICT, ApplicabilityMode.CLASS_ONLY)

    @property
    def model_enforced(self) -> bool:
        return self.mode in (ApplicabilityMode.STRICT, ApplicabilityMode.MODEL_SET)

    @property
    def binding_class_ids(self) -> frozenset[int]:
        """Classes that actually gate in this mode (empty when class is a hint)."""
        return self.class_ids if self.class_enforced else frozenset()

    @property
    def binding_model_ids(self) -> frozenset[int]:
        """Models that actually gate in this mode (empty when model is a hint)."""
        return self.model_ids if self.model_enforced else frozenset()

    @property
    def suggested_class_ids(self) -> frozenset[int]:
        """Non-binding class list — search / UX hints only."""
        return frozenset() if self.class_enforced else self.class_ids

    @property
    def suggested_model_ids(self) -> frozenset[int]:
        """Non-binding model list — search / UX hints only."""
        return frozenset() if self.model_enforced else self.model_ids

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "class_ids": sorted(self.class_ids),
            "model_ids": sorted(self.model_ids),
        }
