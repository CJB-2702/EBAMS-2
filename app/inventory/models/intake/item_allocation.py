from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.inventory.models.intake.enums import (
    AllocationCondition,
    AllocationIntakeMethod,
    AllocationLinkSource,
)


class ItemAllocation(AuditFieldsMixin, SoftDeleteMixin):
    """One physical unit (or counted batch) logged against an IntakeSession.

    `shipment_line = NULL` means unlinked — excess or unmanifested stock
    quarantined in the Intake Room. That is a TERMINAL, ordinary state, not a
    pending task (intake_portal_workflow.md §7.2): a shipment line can never
    be allocated beyond its quantity, so whatever does not fit simply stays
    unlinked and is the allocation portal's business (§7.3).

    THE OVER-ALLOCATION BAN IS NOT EXPRESSIBLE HERE. `sum(live allocations
    linked to line L) <= L.quantity` is an aggregate ACROSS ROWS, so it
    cannot be a `Meta.CheckConstraint`. It is a control-layer invariant
    enforced on every write path that sets `shipment_line`, with the line
    locked for update while the sum is checked and the write applied
    (§7.2, §12.6). It is enforced at WRITE time, not as a standing
    invariant — if procurement later reduces a line's quantity below what is
    already allocated, the existing rows stand and that is a report, not a
    violation to fix.

    `composite_sn` is `f"{part_id}:{serial_number}"`, written by the control
    layer (never here — models hold no business logic), and is what
    `AllocationValidator` checks for duplicates against both this session's
    other live allocations and existing `ActiveInventory`.
    """

    intake_session = models.ForeignKey(
        "inventory.IntakeSession",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    shipment_line = models.ForeignKey(
        "procurement.ShipmentLine",
        on_delete=models.PROTECT,
        related_name="intake_allocations",
        null=True,
        blank=True,
    )
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="intake_allocations",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    serial_number = models.CharField(max_length=200, blank=True, default="")
    composite_sn = models.CharField(max_length=400, blank=True, default="", db_index=True)
    condition = models.CharField(
        max_length=30,
        choices=AllocationCondition.choices,
        default=AllocationCondition.GOOD,
    )

    # How the COUNT was captured.
    intake_method = models.CharField(
        max_length=30,
        choices=AllocationIntakeMethod.choices,
        default=AllocationIntakeMethod.MANUAL,
    )

    # How the LINK was decided (§12.3) — a different question from
    # `intake_method`, which is why it is a different column. Audit has to be
    # able to separate a machine guess from a human decision.
    link_source = models.CharField(
        max_length=30,
        choices=AllocationLinkSource.choices,
        default=AllocationLinkSource.UNLINKED,
    )
    linked_at = models.DateTimeField(null=True, blank=True)
    linked_by = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    # The literal barcode string as scanned. Kept because when someone
    # disputes a receipt the raw scan is the evidence, and it costs nothing.
    raw_payload = models.CharField(max_length=500, blank=True, default="")

    # "Box crushed", "label unreadable, keyed by hand".
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "inventory_item_allocation"
        ordering = ["intake_session", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="item_allocation_quantity_positive",
            ),
            # A serial identifies ONE physical object; quantity 5 against one
            # serial is meaningless (§6.2). In the database, not only in the
            # control layer.
            models.CheckConstraint(
                condition=models.Q(serial_number="") | models.Q(quantity=1),
                name="item_allocation_serial_implies_unit_qty",
            ),
        ]
        indexes = [
            models.Index(fields=["shipment_line"], name="item_alloc_shp_line_idx"),
            models.Index(fields=["composite_sn"], name="item_alloc_composite_sn_idx"),
        ]

    def __str__(self) -> str:
        serial = f" SN:{self.serial_number}" if self.serial_number else ""
        return f"Allocation #{self.pk}: part {self.part_id} x{self.quantity}{serial} ({self.condition})"
