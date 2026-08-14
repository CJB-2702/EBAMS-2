"""Context: the entry point for control logic around one package_id."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.guards.package_state_guard import (
    PackageStateMachine,
)
from app.procurement.control_layer.handlers.package_line_split_handler import (
    PackageLineSplitHandler,
)
from app.procurement.control_layer.managers.package_line_manager import (
    PackageLineManager,
)
from app.procurement.control_layer.managers.package_status_manager import (
    PackageStatusManager,
)
from app.procurement.control_layer.narrators.package_narrator import PackageNarrator
from app.procurement.models import Package, PackageStatus, PurchaseOrderStatus


class PackageContext:
    def __init__(self, package_id: int) -> None:
        self.package_id = package_id
        self._package: Package | None = None

    @property
    def package(self) -> Package:
        if self._package is None:
            self._package = Package.objects.select_related("purchase_order").get(
                pk=self.package_id
            )
        return self._package

    def advance(self, *, to_status: str, actor=None) -> list[int]:
        """Move the package's status and propagate to the demands behind it.

        Returns the ids of demands whose shipment_state moved.
        """
        package = self.package
        verdict = PackageStateMachine.check(
            from_status=package.status, to_status=to_status
        )
        if not verdict.allowed:
            raise ProcurementValidationError([verdict.reason])

        with transaction.atomic():
            previous = package.status
            package.status = to_status
            package.updated_by = actor
            package.save(update_fields=["status", "updated_by", "updated_at"])

            moved = PackageStatusManager.propagate_shipment_state(
                package=package, actor=actor
            )

            PackageNarrator.post(
                package=package,
                message=PackageNarrator.status_changed(
                    from_status=previous, to_status=to_status
                ),
                actor=actor,
            )

            # Any accepted quantity against a Placed PO makes it Partially
            # Received — that part IS computed. Only the terminal close-out is
            # human (D29).
            if to_status == PackageStatus.ACCEPTED:
                self._mark_order_partially_received(actor=actor)

        return moved

    # ------------------------------------------------------------------ #
    # The audited-mutation rule
    # ------------------------------------------------------------------ #

    #: A package at or past local delivery, or one carrying a split, is a
    #: physical record rather than a plan. It stays fully mutable — nothing is
    #: blocked — but every change to it costs a mandatory human comment plus a
    #: pre-state snapshot on the package's own Event, written in the same
    #: request as the change (D69's companion rule).
    AUDITED_STATUSES = frozenset(
        {PackageStatus.DELIVERED_TO_LOCAL, PackageStatus.ACCEPTED}
    )

    @property
    def requires_audit_comment(self) -> bool:
        return (
            self.package.status in self.AUDITED_STATUSES or self.package.has_splits
        )

    def _snapshot(self) -> dict:
        package = self.package
        return {
            "package_number": package.package_number,
            "status": package.status,
            "shipment_id": package.shipment_id,
            "carrier": package.carrier,
            "shipped_date": package.shipped_date,
            "expected_arrival_date": package.expected_arrival_date,
            "notes": package.notes,
            "purchase_order": (
                package.purchase_order.po_number if package.purchase_order_id else None
            ),
            "lines": [
                {
                    "id": line.pk,
                    "part_id": line.part_id,
                    "quantity": line.quantity,
                    "quantity_accepted": line.quantity_accepted,
                    "purchase_order_line_id": line.purchase_order_line_id,
                }
                for line in package.lines.filter(deleted_at__isnull=True)
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
                    "This package has been delivered or split. Changing it "
                    "requires a reason, recorded on the package's history."
                ]
            )
        PackageNarrator.post(
            package=self.package,
            message=PackageNarrator.audited_mutation(
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
        package = self.package
        with transaction.atomic():
            self._audit(action="Header edited", comment=audit_comment, actor=actor)
            package.shipment_id = shipment_id
            package.carrier = carrier
            package.shipped_date = shipped_date
            package.expected_arrival_date = expected_arrival_date
            package.notes = notes
            package.updated_by = actor
            package.save(
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
                PackageNarrator.post(
                    package=package,
                    message=PackageNarrator.header_edited(
                        package_number=package.package_number
                    ),
                    actor=actor,
                )
        return package

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
            line = PackageLineManager.add_line(
                package=self.package,
                part_id=part_id,
                quantity=quantity,
                actor=actor,
                purchase_order_line=purchase_order_line,
            )
            PackageNarrator.post(
                package=self.package,
                message=PackageNarrator.line_added(
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

            PackageStatusManager.refresh_mixed_po_assignments(
                package=self.package, actor=actor, commit=True
            )
            PackageNarrator.post(
                package=self.package,
                message=PackageNarrator.line_deleted(
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
            accepted = PackageLineManager.accept(
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
            return PackageLineManager.reassign(
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
            return PackageLineSplitHandler.split(
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
        """Link a PO to a package that was received without one (D71).

        Auto-links every unlinked line to the PO line whose part matches. No
        match, or more than one matching active line, leaves that line
        unlinked — safe failure, never a guess. Same rule create_package
        already applies for copy-on-create (D58's caveat).

        Returns the number of lines that were auto-linked.
        """
        package = self.package
        with transaction.atomic():
            self._audit(
                action="Purchase order attached", comment=audit_comment, actor=actor
            )
            package.purchase_order = purchase_order
            package.updated_by = actor
            package.save(
                update_fields=["purchase_order", "updated_by", "updated_at"]
            )

            linked_count = 0
            for line in package.lines.filter(
                deleted_at__isnull=True, purchase_order_line__isnull=True
            ):
                match = PackageLineManager.resolve_purchase_order_line(
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

            PackageStatusManager.refresh_mixed_po_assignments(
                package=package, actor=actor, commit=True
            )

            PackageNarrator.post(
                package=package,
                message=PackageNarrator.purchase_order_attached(
                    package_number=package.package_number,
                    po_number=purchase_order.po_number,
                    linked_line_count=linked_count,
                ),
                actor=actor,
            )

        return linked_count

    def delete(self, *, actor=None, reason: str = "") -> None:
        """Soft delete the package AND every active line.

        PackageLine.package's CASCADE is a hard-delete cascade and does
        nothing for a soft delete — each active line must be soft-deleted
        explicitly, or it survives as an orphaned "active" row under a
        deleted package.
        """
        package = self.package
        # MANDATORY ALWAYS, not only on a delivered package. A shipment record
        # vanishing with no stated reason is the one case where the history is
        # most needed and least recoverable.
        if not (reason or "").strip():
            raise ProcurementValidationError(
                ["Deleting a package requires a reason."]
            )
        with transaction.atomic():
            now = timezone.now()
            package.lines.filter(deleted_at__isnull=True).update(
                deleted_at=now, updated_by=actor, updated_at=now
            )
            package.deleted_at = now
            package.updated_by = actor
            package.save(update_fields=["deleted_at", "updated_by", "updated_at"])

            PackageNarrator.post(
                package=package,
                message=PackageNarrator.deleted(
                    package_number=package.package_number, reason=reason
                ),
                actor=actor,
            )

    def _mark_order_partially_received(self, *, actor=None) -> None:
        from app.procurement.control_layer.purchase_order_context import (
            PurchaseOrderContext,
        )

        purchase_order = self.package.purchase_order
        if purchase_order is None or purchase_order.status != PurchaseOrderStatus.PLACED:
            return
        PurchaseOrderContext(purchase_order.pk).mark_partially_received(actor=actor)
