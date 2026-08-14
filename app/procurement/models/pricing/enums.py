"""Enums for PartPriceObservation and the PurchaseOrderLine provenance columns
(D87-D92). Values are lowercase snake to match PurchaseOrderStatus /
DemandState elsewhere in this app.
"""

from django.db import models


class PriceSourceType(models.TextChoices):
    PART_CREATE = "part_create", "Part creation"
    QUOTE = "quote", "Quote"
    MANUAL = "manual", "Manual"
    ORDERED = "ordered", "Ordered"
    INVOICED = "invoiced", "Invoiced"
    CATALOG = "catalog", "Catalog"      # reserved; nothing writes it


class PriceConfidence(models.TextChoices):   # D88 — no default; the asserter chooses
    QUOTED = "quoted", "Quoted — I have paper"
    P10 = "p10", "Within ~10%"
    P50 = "p50", "Within ~50%"
    P100 = "p100", "Could be double"
    UNKNOWN = "unknown", "No idea"


class UnitCostSource(models.TextChoices):    # D85 — PurchaseOrderLine
    QUOTED = "quoted", "Quoted"
    LAST_PAID = "last_paid", "Last paid"
    LAST_ORDERED = "last_ordered", "Last ordered"
    ESTIMATED = "estimated", "Estimated"
    UNKNOWN = "unknown", "Unknown"


#: The stored value of an unset unit_cost_source — pre-existing rows from
#: before this build. Follows APPROVAL_STATE_UNSET's precedent.
UNIT_COST_SOURCE_UNSET = ""
