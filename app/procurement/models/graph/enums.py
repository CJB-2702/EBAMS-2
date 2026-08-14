"""GraphSummary.status — a simple derived label, not a weighted composite.

Recomputed the same pass as the eight quantity columns, always by
GraphSummaryManager.recalculate(); never assigned directly by a caller. The
reviewed architecture documents' entropy-score / weighted-drift formula is
deliberately NOT adopted here (D81) — this is a plain, glanceable label.
"""

from django.db import models


class GraphSummaryStatus(models.TextChoices):
    # Nothing outstanding on any axis the graph currently uses.
    BALANCED = "balanced", "Balanced"
    # Demand exists with nothing yet purchased against it.
    AWAITING_PURCHASE = "awaiting_purchase", "Awaiting Purchase"
    # Purchased, nothing shipped/delivered yet.
    AWAITING_SHIPMENT = "awaiting_shipment", "Awaiting Shipment"
    # Delivered, nothing accepted/rejected yet.
    AWAITING_ACCEPTANCE = "awaiting_acceptance", "Awaiting Acceptance"
