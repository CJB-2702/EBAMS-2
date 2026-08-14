"""One recorded assertion that a part cost a particular amount, from a
particular vendor, at a particular time (D79-D92).

Append-only (D80) — rows are written once and never updated. There is no
"current price" anywhere in this schema; current price is resolved by
PartPricePolicy from these rows. Deliberately not SoftDeleteMixin: a wrong
observation is corrected by appending a newer, better one, not by retracting
the old one.
"""

from __future__ import annotations

from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.procurement.models.pricing.enums import PriceConfidence, PriceSourceType


class PartPriceObservation(AuditFieldsMixin):
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="price_observations",
    )
    vendor = models.ForeignKey(
        "procurement.Vendor",
        on_delete=models.PROTECT,
        related_name="price_observations",
    )
    # D87: required, no global tier. A null domain would match for every
    # actor everywhere and let the laziest entry outrank the careful one.
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="part_price_observations",
    )
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="USD")
    # When the price was true, not when the row was written (created_at
    # covers that).
    observed_at = models.DateField()
    source_type = models.CharField(max_length=20, choices=PriceSourceType.choices)
    confidence = models.CharField(max_length=10, choices=PriceConfidence.choices)
    # D89: written True only by an actor holding establish authority for this
    # row's domain, at insert. Never updated — verifying someone else's
    # observation appends a new verified row.
    is_verified = models.BooleanField(default=False)
    source_po_line = models.ForeignKey(
        "procurement.PurchaseOrderLine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="price_observations",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "part_price_observation"
        ordering = ["-observed_at", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="ppo_unit_cost_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__isnull=True) | models.Q(quantity__gt=0),
                name="ppo_quantity_positive_or_null",
            ),
        ]
        indexes = [
            # The chip's two facts: part + vendor, narrowed to visible domains.
            models.Index(
                fields=["part", "vendor", "domain", "-observed_at"],
                name="ppo_part_vendor_domain_idx",
            ),
            # Same, restricted to established prices (D91's second fact).
            models.Index(
                fields=["part", "vendor", "is_verified", "-observed_at"],
                name="ppo_part_vendor_verified_idx",
            ),
            # History page and picker: everything for this part, any vendor.
            models.Index(fields=["part", "-observed_at"], name="ppo_part_recent_idx"),
            # "Everything we have ever been quoted by this vendor."
            models.Index(fields=["vendor", "-observed_at"], name="ppo_vendor_recent_idx"),
        ]
        permissions = [
            (
                "price_establish",
                "Can verify a price observation, making it the established "
                "price for its domain",
            )
        ]

    def __str__(self) -> str:
        return f"{self.part_id} @ {self.unit_cost} ({self.vendor_id}, {self.observed_at})"
