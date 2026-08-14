"""Context: the entry point for control logic around one shipment_id."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.guards.shipment_state_guard import (
    ShipmentStateMachine,
)
from app.procurement.control_layer.handlers.shipment_line_split_handler import (
    ShipmentLineSplitHandler,
)
from app.procurement.control_layer.managers.shipment_line_manager import (
    ShipmentLineManager,
)
from app.procurement.control_layer.managers.shipment_status_manager import (
    ShipmentStatusManager,
)
from app.procurement.control_layer.narrators.shipment_narrator import ShipmentNarrator
from app.procurement.models import Shipment, ShipmentStatus, PurchaseOrderStatus


class ShipmentContext:
    def __init__(self, shipment_id: int) -> None:
        self.shipment_id = shipment_id
        self._shipment: Shipment | None = None

    @property
    def shipment(self) -> Shipment:
        if self._shipment is None:
            self._shipment = Shipment.objects.select_related("purchase_order").get(
                pk=self.shipment_id
            )
        return self._shipment

    def advance(self, *, to_status: str, actor=None) -> list[int]:
        """Move the shipment's status and propagate to the demands behind it.

        Returns the ids of demands whose shipment_state moved.
        """
        shipment = self.shipment
        verdict = ShipmentStateMachine.check(
            from_status=shipment.status, to_status=to_status
        )
        if not verdict.allowed:
            raise ProcurementValidationError([verdict.reason])

        with transaction.atomic():
            previous = shipment.status
            shipment.status = to_status
            shipment.updated_by = actor
            shipment.save(update_fields=["status", "updated_by", "updated_at"])

            moved = ShipmentStatusManager.propagate_shipment_state(
                shipment=shipment, actor=actor
            )

            ShipmentNarrator.post(
                shipment=shipment,
                message=ShipmentNarrator.status_changed(
                    from_status=previous, to_status=to_status
                ),
                actor=actor,
            )

            # Any accepted quantity against a Placed PO makes it Partially
            # Received — that part IS computed. Only the terminal close-out is
            # human (D29).
            if to_status == ShipmentStatus.ACCEPTED:
                self._mark_order_partially_received(actor=actor)

        return moved

    # ------------------------------------------------------------------ #
    # The audited-mutation rule
    # ------------------------------------------------------------------ #

    #: A shipment at or past local delivery, or one carrying a split, is a
    #: physical record rather than a plan. It stays fully mutable — nothing is
    #: blocked — but every change to it costs a mandatory human comment plus a
    #: pre-state snapshot on the shipment's own Event, written in the same
    #: request as the change (D69's companion rule).
    AUDITED_STATUSES = frozenset(
        {ShipmentStatus.DELIVERED_TO_LOCAL, ShipmentStatus.ACCEPTED}
    )

    @property
    def requires_audit_comment(self) -> bool:
        return (
            self.shipment.status in self.AUDITED_STATUSES or self.shipment.has_splits
        )

    def _snapshot(self) -> dict:
        shipment = self.shipment
        return {
            "shipment_number": shipment.shipment_number,
            "status": shipment.status,
            "shipment_id": shipment.shipment_id,
            "carrier": shipment.carrier,
            "shipped_date": shipment.shipped_date,
            "expected_arrival_date": shipment.expected_arrival_date,
            "notes": shipment.notes,
            "purchase_order": (
                shipment.purchase_order.po_number if shipment.purchase_order_id else None
            ),
            "lines": [
                {
                    "id": line.pk,
                    "part_id": line.part_id,
                    "quantity": line.quantity,
                    "quantity_accepted": line.quantity_accepted,
                    "purchase_order_line_id": line.purchase_order_line_id,
                }
                for line in shipment.lines.filter(deleted_at__isnull=True)
            ],
        }

    def _audit(self, *, action: str, comment: str, actor=None) -> None:
        """Post the mandatory comment and the pre-state snapshot.

        Call this BEFORE the write, so the snapshot is genuinely "before".
        One mutation at a time — no batching, no deferral, no supersession
        logic: a deferred audit note is one that gets written from memory.
        """
        if not self.requires_audit_comment:
            return
        if not (comment or "").strip():
            raise ProcurementValidationError(
                [
                    "This shipment has been delivered or split. Changing it "
                    "requires a reason, recorded on the shipment's history."
                ]
            )
        ShipmentNarrator.post(
            shipment=self.shipment,
            message=ShipmentNarrator.audited_mutation(
                action=action, comment=comment.strip(), snapshot=self._snapshot()
            ),
            actor=actor,
        )

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    def update_header(
        self,
        *,
        shipment_id: str = "",
        carrier: str = "",
        shipped_date=None,
        expected_arrival_date=None,
        notes: str = "",
        actor=None,
        audit_comment: str = "",
    ):
        """Header fields only. STATUS IS NOT HERE — advancing status is its own
        action on the view page, the same edit-vs-status-action split the PO
        sector draws."""
        shipment = self.shipment
        with transaction.atomic():
            self._audit(action="Header edited", comment=audit_comment, actor=actor)
            shipment.shipment_id = shipment_id
            shipment.carrier = carrier
            shipment.shipped_date = shipped_date
            shipment.expected_arrival_date = expected_arrival_date
            shipment.notes = notes
            shipment.updated_by = actor
            shipment.save(
                update_fields=[
                    "shipment_id",
                    "carrier",
                    "shipped_date",
                    "expected_arrival_date",
                    "notes",
                    "updated_by",
                    "updated_at",
                ]
            )
            if not self.requires_audit_comment:
                ShipmentNarrator.post(
                    shipment=shipment,
                    message=ShipmentNarrator.header_edited(
                        shipment_number=shipment.shipment_number
                    ),
                    actor=actor,
                )
        return shipment

    def add_line(
        self,
        *,
        part_id: int,
        quantity: Decimal,
        actor=None,
        purchase_order_line=None,
        audit_comment: str = "",
    ):
        with transaction.atomic():
            self._audit(action="Line added", comment=audit_comment, actor=actor)
            line = ShipmentLineManager.add_line(
                shipment=self.shipment,
                part_id=part_id,
                quantity=quantity,
                actor=actor,
                purchase_order_line=purchase_order_line,
            )
            ShipmentNarrator.post(
                shipment=self.shipment,
                message=ShipmentNarrator.line_added(
                    part_number=line.part.part_number,
                    quantity=line.quantity,
                    po_line_number=(
                        purchase_order_line.line_number if purchase_order_line else None
                    ),
                ),
                actor=actor,
            )
            return line

    def delete_line(self, *, line, actor=None, reason: str = "", audit_comment: str = ""):
        """Soft delete one arriving line.

        NEVER BLOCKED, including when the line carries split lineage or an
        accepted quantity — the page warns harder in those cases, but a
        receiver correcting a mis-entered line must not be stuck. The record
        survives as a soft-deleted row plus the narration below.
        """
        with transaction.atomic():
            self._audit(action="Line deleted", comment=audit_comment, actor=actor)
            line.deleted_at = timezone.now()
            line.updated_by = actor
            line.save(update_fields=["deleted_at", "updated_by", "updated_at"])

            ShipmentStatusManager.refresh_mixed_po_assignments(
                shipment=self.shipment, actor=actor, commit=True
            )
            ShipmentNarrator.post(
                shipment=self.shipment,
                message=ShipmentNarrator.line_deleted(
                    part_number=line.part.part_number,
                    quantity=line.quantity,
                    reason=reason,
                ),
                actor=actor,
            )
        return line

    def accept_line(
        self, *, line, quantity_accepted: Decimal, actor=None, rejection_notes: str = ""
    ):
        with transaction.atomic():
            accepted = ShipmentLineManager.accept(
                line=line,
                quantity_accepted=quantity_accepted,
                actor=actor,
                rejection_notes=rejection_notes,
            )
            self._mark_order_partially_received(actor=actor)
            return accepted

    def reassign_line(
        self, *, line, purchase_order_line, actor=None, audit_comment: str = ""
    ):
        with transaction.atomic():
            self._audit(action="Line reassigned", comment=audit_comment, actor=actor)
            return ShipmentLineManager.reassign(
                line=line, purchase_order_line=purchase_order_line, actor=actor
            )

    def split_line(
        self,
        *,
        line,
        quantity: Decimal,
        purchase_order_line,
        actor=None,
        audit_comment: str = "",
    ):
        with transaction.atomic():
            self._audit(action="Line split", comment=audit_comment, actor=actor)
            return ShipmentLineSplitHandler.split(
                line=line,
                quantity=quantity,
                purchase_order_line=purchase_order_line,
                actor=actor,
            )

    def assign_line(
        self,
        *,
        line,
        purchase_order_line,
        quantity: Decimal | None = None,
        actor=None,
        audit_comment: str = "",
    ):
        """Point some or all of an arriving line at a PO line.

        The split-vs-reassign choice is made HERE rather than by the caller,
        because it is one decision from the user's side — "this much of this
        line belongs to that order line" — and making a view pick between two
        control-layer verbs is how the two paths drift apart. A full-quantity
        assignment is a reassignment (no new row, `has_splits` untouched);
        anything less is a genuine split.
        """
        if quantity is None or quantity >= line.quantity:
            return self.reassign_line(
                line=line,
                purchase_order_line=purchase_order_line,
                actor=actor,
                audit_comment=audit_comment,
            )
        return self.split_line(
            line=line,
            quantity=quantity,
            purchase_order_line=purchase_order_line,
            actor=actor,
            audit_comment=audit_comment,
        )

    def attach_purchase_order(
        self, *, purchase_order, actor=None, audit_comment: str = ""
    ) -> int:
        """Link a PO to a shipment that was received without one (D71).

        Auto-links every unlinked line to the PO line whose part matches. No
        match, or more than one matching active line, leaves that line
        unlinked — safe failure, never a guess. Same rule create_shipment
        already applies for copy-on-create (D58's caveat).

        Returns the number of lines that were auto-linked.
        """
        shipment = self.shipment
        with transaction.atomic():
            self._audit(
                action="Purchase order attached", comment=audit_comment, actor=actor
            )
            shipment.purchase_order = purchase_order
            shipment.updated_by = actor
            shipment.save(
                update_fields=["purchase_order", "updated_by", "updated_at"]
            )

            linked_count = 0
            for line in shipment.lines.filter(
                deleted_at__isnull=True, purchase_order_line__isnull=True
            ):
                match = ShipmentLineManager.resolve_purchase_order_line(
                    purchase_order=purchase_order, part_id=line.part_id
                )
                if match is None:
                    continue
                line.purchase_order_line = match
                line.updated_by = actor
                line.save(
                    update_fields=["purchase_order_line", "updated_by", "updated_at"]
                )
                linked_count += 1

            ShipmentStatusManager.refresh_mixed_po_assignments(
                shipment=shipment, actor=actor, commit=True
            )

            ShipmentNarrator.post(
                shipment=shipment,
                message=ShipmentNarrator.purchase_order_attached(
                    shipment_number=shipment.shipment_number,
                    po_number=purchase_order.po_number,
                    linked_line_count=linked_count,
                ),
                actor=actor,
            )

        return linked_count

    def delete(self, *, actor=None, reason: str = "") -> None:
        """Soft delete the shipment AND every active line.

        ShipmentLine.shipment's CASCADE is a hard-delete cascade and does
        nothing for a soft delete — each active line must be soft-deleted
        explicitly, or it survives as an orphaned "active" row under a
        deleted shipment.
        """
        shipment = self.shipment
        # MANDATORY ALWAYS, not only on a delivered shipment. A shipment record
        # vanishing with no stated reason is the one case where the history is
        # most needed and least recoverable.
        if not (reason or "").strip():
            raise ProcurementValidationError(
                ["Deleting a shipment requires a reason."]
            )
        with transaction.atomic():
            now = timezone.now()
            shipment.lines.filter(deleted_at__isnull=True).update(
                deleted_at=now, updated_by=actor, updated_at=now
            )
            shipment.deleted_at = now
            shipment.updated_by = actor
            shipment.save(update_fields=["deleted_at", "updated_by", "updated_at"])

            ShipmentNarrator.post(
                shipment=shipment,
                message=ShipmentNarrator.deleted(
                    shipment_number=shipment.shipment_number, reason=reason
                ),
                actor=actor,
            )

    def _mark_order_partially_received(self, *, actor=None) -> None:
        from app.procurement.control_layer.purchase_order_context import (
            PurchaseOrderContext,
        )

        purchase_order = self.shipment.purchase_order
        if purchase_order is None or purchase_order.status != PurchaseOrderStatus.PLACED:
            return
        PurchaseOrderContext(purchase_order.pk).mark_partially_received(actor=actor)
