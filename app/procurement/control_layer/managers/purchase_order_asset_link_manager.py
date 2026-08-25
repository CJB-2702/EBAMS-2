"""Manager: mirrors onto a PO's Event every asset its demands' events are about.

A PurchaseOrder has no assets relationship of its own and does not need one —
it already owns exactly one Event (D17-D19), and AssetEvent is where the
events app records "which assets is this event about". So the PO's asset set
is stored the same way everything else's is: AssetEvent rows on po.event,
under this manager's own role.

WHERE THE ASSETS COME FROM. A demand may carry an `event` FK back to whatever
raised it — a maintenance job, a dispatch. That event knows its assets. So:

    PO -> its lines -> their active demand links -> each demand's event
       -> that event's assets -> unique set -> AssetEvent rows on PO.event

TECH DEBT, ACKNOWLEDGED AND ACCEPTED (not an oversight — a decision).
This is a snapshot refreshed only when a demand is allocated to this PO. It
goes stale in at least three known ways:

  * a demand is de-linked or released — its assets stay on the PO
  * a demand's `event` FK is repointed afterwards
  * the source event gains or loses an asset after allocation

None of those re-run this. The alternative is a listener on three tables in
two other apps to keep a convenience read exact, which costs more than the
drift does: this set answers "roughly what kit is this order for", it is not
an authority anything transacts against. The demand links remain the truth.

De-linking is the one case worth naming twice, because ``sync_role`` would
in fact clean it up — but nothing calls this on the de-link path, deliberately.
Adding that call is the cheap first fix if the drift ever starts to bite.
"""

from __future__ import annotations

from app.events.control_layer.managers.asset_event_link_manager import (
    AssetEventLinkManager,
)
from app.procurement.models import PurchaseOrderDemandLink

# Ours alone. sync_role only ever deletes rows carrying this exact role, so a
# "target" link maintenance wrote on some shared event is never touched here.
PURCHASE_ORDER_ASSET_ROLE = "purchase_order_subject"


class PurchaseOrderAssetLinkManager:
    @classmethod
    def refresh(cls, *, purchase_order, actor=None) -> set[int]:
        """Recompute the PO event's asset links from its demands. Returns the
        resulting asset id set.

        A PO with no event yet (inside the factory's own transaction, before
        the FK is set) is a no-op rather than an error — the factory creates
        the event before any demand can be linked, so this never silently
        skips real work.
        """
        if purchase_order.event_id is None:
            return set()

        asset_ids = cls.collect_asset_ids(purchase_order=purchase_order)
        AssetEventLinkManager.sync_role(
            event_id=purchase_order.event_id,
            asset_ids=asset_ids,
            role=PURCHASE_ORDER_ASSET_ROLE,
            actor=actor,
        )
        return asset_ids

    @classmethod
    def collect_asset_ids(cls, *, purchase_order) -> set[int]:
        """The unique assets of every event behind this PO's active demands.

        Active only: a released allocation (is_active=False) is history, and a
        soft-deleted one was a mistake. Neither describes what this order is
        currently for.
        """
        event_ids = set(
            PurchaseOrderDemandLink.objects.filter(
                purchase_order_line__purchase_order=purchase_order,
                is_active=True,
                deleted_at__isnull=True,
                part_demand__event_id__isnull=False,
            ).values_list("part_demand__event_id", flat=True)
        )
        if not event_ids:
            return set()
        return AssetEventLinkManager.asset_ids_for_events(event_ids=event_ids)
