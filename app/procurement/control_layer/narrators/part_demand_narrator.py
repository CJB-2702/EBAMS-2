"""Narrator: human-readable journal and audit text for the demand side."""

from __future__ import annotations

from app.procurement.models import (
    PURCHASING_STATE_UNSET,
    DemandDimension,
    DemandState,
    IssuanceState,
    PurchasingState,
    ShipmentState,
)

_LABELS: dict[str, dict[str, str]] = {
    DemandDimension.DEMAND: dict(DemandState.choices),
    DemandDimension.PURCHASING: dict(PurchasingState.choices),
    DemandDimension.SHIPMENT: dict(ShipmentState.choices),
    DemandDimension.ISSUANCE: dict(IssuanceState.choices),
}

_DIMENSION_LABELS: dict[str, str] = dict(DemandDimension.choices)

_UNSET_LABEL = "No decision"


class PartDemandNarrator:
    @classmethod
    def stage_label(cls, *, dimension: str, stage: str) -> str:
        if dimension == DemandDimension.PURCHASING and stage == PURCHASING_STATE_UNSET:
            return _UNSET_LABEL
        return _LABELS.get(dimension, {}).get(stage, stage or _UNSET_LABEL)

    @classmethod
    def initialized(cls, *, dimension: str, stage: str) -> str:
        return (
            f"{_DIMENSION_LABELS.get(dimension, dimension)} initialized at "
            f"'{cls.stage_label(dimension=dimension, stage=stage)}'."
        )

    @classmethod
    def transitioned(
        cls, *, dimension: str, from_stage: str, to_stage: str
    ) -> str:
        return (
            f"{_DIMENSION_LABELS.get(dimension, dimension)} moved from "
            f"'{cls.stage_label(dimension=dimension, stage=from_stage)}' to "
            f"'{cls.stage_label(dimension=dimension, stage=to_stage)}'."
        )

    @classmethod
    def auto_completed(cls) -> str:
        return (
            "Automatically completed: purchasing has cleared and the material has "
            "been issued."
        )

    @classmethod
    def auto_approved_by_link(cls, *, po_number: str) -> str:
        return f"Approved automatically when allocated to purchase order {po_number}."

    @classmethod
    def purchasing_reset_by_line_cancellation(cls, *, po_number: str) -> str:
        return (
            f"Purchasing decision cleared: the line on purchase order {po_number} "
            f"that was going to buy this was cancelled."
        )

    @classmethod
    def released_by_po_cancellation(cls, *, po_number: str) -> str:
        return f"Purchase order {po_number} was cancelled."

    @classmethod
    def propagated_from_purchase_order(cls, *, po_number: str) -> str:
        return f"Followed from purchase order {po_number}."

    @classmethod
    def propagated_from_shipment(cls, *, shipment_number: str) -> str:
        return f"Followed from shipment {shipment_number}."

    @classmethod
    def issuance_recorded(cls, *, net_issued_qty) -> str:
        return f"Issuance recorded. Net quantity now with the requester: {net_issued_qty}."
