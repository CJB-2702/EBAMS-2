"""Policy: which shipment line, if any, a freshly recorded scan belongs to
(intake_portal_workflow.md §5.2).

    Scan arrives
      -> record the allocation                      ALWAYS SUCCEEDS
      -> part number on exactly ONE line in the whole session manifest?
             yes -> link, auto_single_match
             no  -> is an active shipment set?
                        no  -> leave unlinked
                        yes -> part on a line of the active shipment,
                               and that line under its cap ACROSS ALL SESSIONS?
                                   yes -> link, auto_active_package
                                   no  -> leave unlinked

SILENT NON-ASSOCIATION IS THE DEFAULT AND CORRECT OUTCOME. Auto-linking is a
convenience, not a requirement. The operator is NEVER shown a linking failure,
never blocked, and never asked to resolve ambiguity while holding a box —
that is the rule that keeps the record page usable at speed (§5.3).
Everything left unlinked flows to the allocation portal (§7.3), which exists
precisely to handle it.

The active shipment's ONLY job is to break ties (§5.1). When a part number
appears on more than one shipment in the manifest, it says which shipment the
operator is physically standing in front of. It is not a filter and not a
scope — a unique match anywhere in the manifest still wins, because it needs
no tie broken.

The quantity cap in step 3 is not an auto-association nicety. It is the
universal over-allocation rule (§7.2) applied here like everywhere else, and
it counts EVERY session's rows — otherwise session 2 would cheerfully link
another 50 units onto a line session 1 already filled, manufacturing an
overage out of nothing (§5.5).

This replaces `IntakeMatchingManager.find_target_line` and its FIFO cascade,
an older policy that knew nothing about the active shipment and applied no
cap.
"""

from __future__ import annotations

from decimal import Decimal

from app.inventory.control_layer.managers.allocation_link_manager import (
    AllocationLinkManager,
)
from app.inventory.models.intake.enums import AllocationLinkSource


class AutoAssociationPolicy:
    @classmethod
    def _manifest_lines(cls, *, session, part_id: int, shipment_id: int | None = None):
        """Live lines for this part on the session's shipments, oldest first.

        Ordered by id so the choice is deterministic — two operators scanning
        the same part in the same state get the same answer, which matters
        for an operation nobody is watching.
        """
        from app.procurement.models import ShipmentLine

        shipment_ids = list(
            session.shipment_associations.filter(deleted_at__isnull=True).values_list(
                "shipment_id", flat=True
            )
        )
        if shipment_id is not None:
            shipment_ids = [s for s in shipment_ids if s == shipment_id]
        if not shipment_ids:
            return []
        return list(
            ShipmentLine.objects.filter(
                shipment_id__in=shipment_ids, part_id=part_id, deleted_at__isnull=True
            )
            .select_related("shipment", "part")
            .order_by("id")
        )

    @classmethod
    def decide(cls, *, session, part_id: int, quantity: Decimal) -> tuple[int | None, str]:
        """Return `(shipment_line_id_or_None, link_source)`.

        NEVER RAISES. A linking decision must not be able to fail a count.
        Every "no" in the flowchart lands on the same quiet answer: unlinked.
        """
        unlinked = (None, AllocationLinkSource.UNLINKED)

        manifest = cls._manifest_lines(session=session, part_id=part_id)
        if not manifest:
            return unlinked

        # 1. Unambiguous: exactly one line in the WHOLE manifest wants this
        #    part. No tie to break, so the active shipment is irrelevant here.
        if len(manifest) == 1:
            line = manifest[0]
            if AllocationLinkManager.fits(shipment_line_id=line.pk, quantity=quantity):
                return line.pk, AllocationLinkSource.AUTO_SINGLE_MATCH
            return unlinked

        # 2. Ambiguous. Only the active shipment can break the tie.
        if session.active_shipment_id is None:
            return unlinked

        for line in cls._manifest_lines(
            session=session, part_id=part_id, shipment_id=session.active_shipment_id
        ):
            if AllocationLinkManager.fits(shipment_line_id=line.pk, quantity=quantity):
                return line.pk, AllocationLinkSource.AUTO_ACTIVE_PACKAGE

        return unlinked
