"""Struct: the result of reconciling an uploaded layout SVG's shape codes
against a tier's existing targets (FD-23/FD-29). Used by both the Room-tier
upload (targets = `RoomLocation.display_code`) and the RoomLocation-tier
upload (targets = `StorageLocation.atomic_coord`) — same shape either way.

No auto-create/delete happens from an upload alone: the reconciliation
screen is the only path that turns `unmatched_shapes` into real rows (via
`RoomLocationBulkFactory`/`StorageLocationBulkFactory`), and `orphaned`
targets are surfaced, never silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SvgReconciliationStruct:
    matched: tuple[str, ...]
    unmatched_shapes: tuple[str, ...]
    orphaned: tuple[str, ...]

    @classmethod
    def build(cls, *, shape_codes: list[str], existing_codes: set[str]) -> "SvgReconciliationStruct":
        shape_set = set(shape_codes)
        return cls(
            matched=tuple(sorted(shape_set & existing_codes)),
            unmatched_shapes=tuple(sorted(shape_set - existing_codes)),
            orphaned=tuple(sorted(existing_codes - shape_set)),
        )

    def to_dict(self) -> dict:
        return {
            "matched": list(self.matched),
            "unmatched_shapes": list(self.unmatched_shapes),
            "orphaned": list(self.orphaned),
        }
