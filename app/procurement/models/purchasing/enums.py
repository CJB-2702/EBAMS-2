"""PurchaseOrder's own lifecycle as a commercial document (D27).

Distinct from — but the thing that drives — each linked demand's
purchasing_state and shipment_state (D40). A separate enum from the demand
axes because the two lifecycles are genuinely independent: a PO is a document
with a vendor, a demand is a need with a requester.
"""

from django.db import models


class PurchaseOrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PLACED = "placed", "Placed"
    PARTIALLY_RECEIVED = "partially_received", "Partially Received"
    RECEIVED = "received", "Received"
    CANCELLED = "cancelled", "Cancelled"


class PurchaseOrderApprovalState(models.TextChoices):
    """A separate axis from status (D71/D76) — "has a manager blessed this"
    and "where is this order in the world" are different questions, the same
    reason PartDemand carries four axes rather than one.

    The stored default is "" (blank), not a member of this enum — blank is a
    real, meaningful value meaning "not yet submitted", following D65's
    precedent on PurchasingState. Approved is not revocable through this axis;
    an approved order is cancelled through status instead.

        Unsubmitted -> Pending Approval -> Approved
             |               |
           Denied / Cancelled (reachable from either non-terminal state)
    """

    PENDING_APPROVAL = "pending_approval", "Pending Approval"
    APPROVED = "approved", "Approved"
    DENIED = "denied", "Denied"
    CANCELLED = "cancelled", "Cancelled"


#: The stored value of an unset ``approval_state`` — "Unsubmitted".
APPROVAL_STATE_UNSET = ""
