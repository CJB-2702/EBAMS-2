"""Guard types for Phase 6 issuance. Source-room domain access is already
enforced by `StockLedgerManager.withdraw` on every call, same as movements
(part_issues.md §4) — this guard adds the functional `can_issue_parts`
permission plus the recipient-shape check the model's CheckConstraints also
carry (belt-and-suspenders so a bad request reads as a message, not a 500).
"""

from __future__ import annotations

from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.guards.stock_guard import StockPolicy
from app.inventory.models.issuance.enums import IssueType


class IssuanceValidator:
    @classmethod
    def check_recipient_shape(
        cls,
        *,
        issue_type: str,
        demand_id: int | None,
        issued_to_id: int | None,
        issued_to_asset_id: int | None,
    ) -> None:
        if issue_type == IssueType.FOR_PART_DEMAND and demand_id is None:
            raise InventoryValidationError(
                ["A demand-linked issue requires a part demand."]
            )
        if not any([demand_id, issued_to_id, issued_to_asset_id]):
            raise InventoryValidationError(
                ["An issue needs at least one recipient: demand, asset, or user."]
            )


class IssuancePolicy:
    @classmethod
    def check_can_issue(cls, *, actor) -> None:
        StockPolicy.check_permission(
            actor=actor, permission_codename="inventory.can_issue_parts"
        )
