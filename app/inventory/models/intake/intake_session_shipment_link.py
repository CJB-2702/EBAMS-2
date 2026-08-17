from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class IntakeSessionShipmentLink(AuditFieldsMixin, SoftDeleteMixin):
    """Join row: which shipments an IntakeSession is receiving against.

    Kit name `ScanningSessionShipmentAssociation` shortened to this repo's
    link-table convention; behavior is identical. Soft-deletable so
    `IntakeContext.cancel_session`'s sweep can retract associations the same
    way it retracts allocations, even though the row carries no independent
    business state of its own.
    """

    intake_session = models.ForeignKey(
        "inventory.IntakeSession",
        on_delete=models.CASCADE,
        related_name="shipment_associations",
    )
    shipment = models.ForeignKey(
        "procurement.Shipment",
        on_delete=models.PROTECT,
        related_name="intake_session_links",
    )

    class Meta:
        db_table = "inventory_intake_session_shipment_link"
        ordering = ["intake_session", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["intake_session", "shipment"],
                name="uniq_intake_session_shipment",
            ),
        ]

    def __str__(self) -> str:
        return f"IntakeSession #{self.intake_session_id} <-> Shipment #{self.shipment_id}"
