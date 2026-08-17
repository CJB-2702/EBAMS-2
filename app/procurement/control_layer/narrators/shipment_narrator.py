"""Narrator: machine-comment text for a shipment's own Event stream (D68).

Shipment-lifecycle machine comments move here from the PO's Event — a shipment
now has its own Event row for its whole lifetime, same shape as
PurchaseOrderNarrator. A split landing on a DIFFERENT PO's line still
additionally narrates on that other PO's Event via PurchaseOrderNarrator,
because that PO's own story changed too.
"""

from __future__ import annotations

from app.events.models import Comment


class ShipmentNarrator:
    @classmethod
    def post(cls, *, shipment, message: str, actor=None) -> Comment | None:
        """Post a machine comment to the shipment's Event. No-op if the shipment
        has no Event, which the factory makes impossible in practice."""
        if shipment.event_id is None:
            return None
        return Comment.objects.create(
            activity_thread_id=shipment.event_id,
            content=message,
            is_human_made=False,
            revision=1,
            created_by=actor,
            updated_by=actor,
        )

    # ------------------------------------------------------------------ #
    # Message text
    # ------------------------------------------------------------------ #

    @staticmethod
    def created(*, shipment_number: str, line_count: int, purchase_order_number: str = "") -> str:
        if purchase_order_number:
            return (
                f"Shipment {shipment_number} recorded with {line_count} line(s) "
                f"against {purchase_order_number}."
            )
        return (
            f"Shipment {shipment_number} received with {line_count} line(s), no "
            f"purchase order on file yet."
        )

    @staticmethod
    def purchase_order_attached(
        *, shipment_number: str, po_number: str, linked_line_count: int
    ) -> str:
        return (
            f"Shipment {shipment_number} attached to purchase order {po_number}. "
            f"{linked_line_count} line(s) auto-linked to a matching PO line."
        )

    @staticmethod
    def status_changed(*, from_status: str, to_status: str) -> str:
        return f"Status changed from '{from_status}' to '{to_status}'."

    @staticmethod
    def line_accepted(*, part_number: str, quantity, quantity_accepted) -> str:
        return f"{part_number} shipped {quantity}, accepted {quantity_accepted}."

    @staticmethod
    def line_allocated(*, part_number: str, quantity, target_line_number: int) -> str:
        return f"{quantity} x {part_number} allocated to line {target_line_number}."

    @staticmethod
    def allocation_released(
        *, part_number: str, quantity, target_line_number: int
    ) -> str:
        return (
            f"{quantity} x {part_number} released from line {target_line_number} "
            f"and returned to this shipment's unallocated quantity."
        )

    @staticmethod
    def quantity_edited(*, part_number: str, old_quantity, new_quantity) -> str:
        return f"{part_number}: shipped quantity corrected from {old_quantity} to {new_quantity}."

    @staticmethod
    def claim_auto_updated_by_shortfall(
        *, target_line_number: int, old_quantity, new_quantity
    ) -> str:
        return (
            f"Shipped quantity reduced; the allocation to line {target_line_number} "
            f"was the only active, unlocked claim, so it was automatically "
            f"updated from {old_quantity} to {new_quantity}."
        )

    @staticmethod
    def claim_unlocked(*, target_line_number: int) -> str:
        return (
            f"The LOCKED allocation to line {target_line_number} was deliberately "
            f"unlocked through the Reallocation Portal's two-popup confirmation."
        )

    @staticmethod
    def reallocation_committed(*, new_quantity) -> str:
        return (
            f"Reallocation resolved through the Reallocation Portal; shipped "
            f"quantity now {new_quantity}."
        )

    @staticmethod
    def line_split(
        *,
        part_number: str,
        old_quantity,
        received_qty,
        remaining_qty,
        new_line_id: int,
    ) -> str:
        return (
            f"{part_number}: partial receipt of {received_qty} (of {old_quantity} "
            f"shipped) closed this line. Remaining {remaining_qty} split onto new "
            f"line #{new_line_id}, still awaiting delivery."
        )

    @staticmethod
    def line_added(*, part_number: str, quantity, po_line_number: int | None) -> str:
        target = (
            f"allocated to line {po_line_number}"
            if po_line_number
            else "not allocated to any order line yet"
        )
        return f"Line added: {quantity} x {part_number}, {target}."

    @staticmethod
    def line_deleted(*, part_number: str, quantity, reason: str) -> str:
        text = f"Line removed: {quantity} x {part_number}."
        return f"{text} Reason: {reason}" if reason else text

    @staticmethod
    def header_edited(*, shipment_number: str) -> str:
        return f"Header details edited on shipment {shipment_number}."

    @staticmethod
    def audited_mutation(*, action: str, comment: str, snapshot: dict) -> str:
        """The mandatory-comment record for mutating a delivered or split
        shipment (D69's companion rule on the edit page).

        The human comment leads, because that is the part a person reads six
        months later. The pre-state snapshot follows as JSON on its own line so
        the detail page's comment card can collapse it — an audit trail nobody
        can read is not an audit trail, and a raw dict inlined in the feed
        buries every human comment around it.
        """
        import json

        return (
            f"{action} on a delivered or split shipment.\n"
            f"Reason given: {comment}\n"
            f"State before the change: {json.dumps(snapshot, default=str, sort_keys=True)}"
        )

    @staticmethod
    def deleted(*, shipment_number: str, reason: str) -> str:
        text = f"Shipment {shipment_number} deleted."
        return f"{text} Reason: {reason}" if reason else text
