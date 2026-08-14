"""The event payload: IDS AND SCALARS ONLY, never model instances.

A future out-of-process listener — a webhook, an ERP push, an email job — must
be able to consume this unchanged. Passing a model instance would make that
impossible and would let a listener issue queries against a transaction it
knows nothing about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.procurement.presentation_layer.tools.po_events.events import (
    PurchaseOrderEventType,
)


@dataclass(frozen=True)
class PurchaseOrderEventPayload:
    event_type: PurchaseOrderEventType
    purchase_order_id: int
    po_number: str
    status: str
    occurred_at: datetime
    previous_status: str = ""
    actor_id: int | None = None
    affected_demand_ids: tuple[int, ...] = field(default_factory=tuple)
