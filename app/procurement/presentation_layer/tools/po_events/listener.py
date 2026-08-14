"""The listener interface — DEFINED, NOT IMPLEMENTED.

Zero concrete listeners ship in this build. This is scaffolding placed
deliberately: the shape is what matters, so adding a webhook or an email push
later requires no change to any write path.

Chosen over D20's original Django signal because signals are stringly-typed,
hard to enumerate, and hide their subscribers, while an explicit registry makes
"what listens to POs" answerable by reading one file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.procurement.presentation_layer.tools.po_events.events import (
    PurchaseOrderEventType,
)
from app.procurement.presentation_layer.tools.po_events.payload import (
    PurchaseOrderEventPayload,
)


class PurchaseOrderEventListener(ABC):
    @abstractmethod
    def handles(self, event_type: PurchaseOrderEventType) -> bool:
        """Return True if this listener wants the given event type."""

    @abstractmethod
    def handle(self, payload: PurchaseOrderEventPayload) -> None:
        """Do the work. MUST NOT raise into the caller — the emitter catches,
        but a listener that throws is still a bug."""
