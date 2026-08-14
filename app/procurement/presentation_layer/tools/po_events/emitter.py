"""The emitter. Fires on PO create and on each status change (D48).

Three rules, all of them load-bearing:

  1. FIRE AND FORGET. A listener raising must never fail the write that emitted
     it. The emitter catches, logs, and continues. A PO does not fail to be
     placed because an email server is down.
  2. EMIT AFTER COMMIT, never inside the transaction — a listener must never
     observe a PO that then rolls away.
  3. THE PAYLOAD CARRIES IDS AND SCALARS ONLY (see payload.py).

This is OUTBOUND ONLY. It is not the deferred inbound integration API (D16),
which needs a payload contract, a status vocabulary, and a service-account auth
model, none of which exist. They will meet eventually; they are not the same
seam.
"""

from __future__ import annotations

import logging

from django.db import transaction

from app.procurement.presentation_layer.tools.po_events.payload import (
    PurchaseOrderEventPayload,
)
from app.procurement.presentation_layer.tools.po_events.registry import (
    registered_listeners,
)

logger = logging.getLogger("app.procurement.po_events")


class PurchaseOrderEventEmitter:
    @classmethod
    def emit(cls, payload: PurchaseOrderEventPayload) -> None:
        """Queue the payload for dispatch after the current transaction
        commits. With zero listeners registered this costs one empty loop."""
        transaction.on_commit(lambda: cls._dispatch(payload))

    @classmethod
    def _dispatch(cls, payload: PurchaseOrderEventPayload) -> None:
        for listener in registered_listeners():
            try:
                if listener.handles(payload.event_type):
                    listener.handle(payload)
            except Exception:  # noqa: BLE001 — deliberately swallowed, see above
                logger.exception(
                    "Purchase order event listener %s failed handling %s for PO %s",
                    type(listener).__name__,
                    payload.event_type,
                    payload.purchase_order_id,
                )
