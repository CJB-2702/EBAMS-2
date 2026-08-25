"""Manager: the one place AssetEvent join rows are written and read in bulk.

AssetEvent is the events app's own answer to "which assets is this event
about". Several sub-apps had been recording that answer only in their own
detail table (MaintenanceDetail.asset, AssetReservation.asset) and never
writing the join row, which left the events portal unable to see the link and
left every other app reading a maintenance-shaped column to find an asset.
This manager closes that gap: producers call ``link``/``sync_role`` when they
commit an asset to an event, consumers call ``asset_ids_for_events``.

``role`` is a free string, not an enum — the vocabulary is per-producer
("target", "reserved_unit", "purchase_order_subject") and a shared enum would
force every app to agree on words that only matter inside one of them.
"""

from __future__ import annotations

from app.events.models.asset_event import AssetEvent


class AssetEventLinkManager:
    @classmethod
    def link(cls, *, asset_id: int, event_id: int, role: str = "", actor=None) -> AssetEvent | None:
        """Idempotent. Returns None for a missing asset_id/event_id rather than
        raising — a producer with no asset committed yet is the normal case,
        not an error."""
        if not asset_id or not event_id:
            return None
        link, created = AssetEvent.objects.get_or_create(
            asset_id=asset_id,
            event_id=event_id,
            defaults={"role": role, "created_by": actor, "updated_by": actor},
        )
        # An existing link with no role yet gains one; a link that already
        # names a role keeps it. Two producers can legitimately point at the
        # same pair and the first one to say why wins.
        if not created and role and not link.role:
            link.role = role
            link.updated_by = actor
            link.save(update_fields=["role", "updated_by", "updated_at"])
        return link

    @classmethod
    def link_many(
        cls, *, asset_ids, event_id: int, role: str = "", actor=None
    ) -> list[AssetEvent]:
        return [
            created
            for asset_id in dict.fromkeys(asset_ids)
            if (created := cls.link(asset_id=asset_id, event_id=event_id, role=role, actor=actor))
        ]

    @classmethod
    def sync_role(
        cls, *, event_id: int, asset_ids, role: str, actor=None
    ) -> tuple[int, int]:
        """Make this event's links *for this role* exactly ``asset_ids``.

        Scoped to one role on purpose: an event can carry links written by
        several producers, and a producer that owns "purchase_order_subject"
        has no business deleting the "target" link maintenance wrote.

        Returns (added, removed).
        """
        wanted = {int(a) for a in asset_ids if a}
        existing = dict(
            AssetEvent.objects.filter(event_id=event_id, role=role).values_list(
                "asset_id", "pk"
            )
        )

        stale = [pk for asset_id, pk in existing.items() if asset_id not in wanted]
        removed = 0
        if stale:
            removed = AssetEvent.objects.filter(pk__in=stale).delete()[0]

        added = 0
        for asset_id in wanted - existing.keys():
            if cls.link(asset_id=asset_id, event_id=event_id, role=role, actor=actor):
                added += 1
        return added, removed

    @classmethod
    def asset_ids_for_events(cls, *, event_ids) -> set[int]:
        """Every asset any of these events is about.

        Unions the join table with MaintenanceDetail.asset because historical
        maintenance rows predate the join row being written (and the column
        stays authoritative for that one app either way). Both tables live in
        the events app, so this stays inside its own boundary.
        """
        event_ids = [int(e) for e in event_ids if e]
        if not event_ids:
            return set()

        from app.events.models.details import MaintenanceDetail

        return set(
            AssetEvent.objects.filter(event_id__in=event_ids).values_list(
                "asset_id", flat=True
            )
        ) | set(
            MaintenanceDetail.objects.filter(
                pk__in=event_ids, asset_id__isnull=False
            ).values_list("asset_id", flat=True)
        )

    @classmethod
    def event_ids_for_asset(cls, *, asset_id: int) -> set[int]:
        """The inverse read, used by the events list's asset filter."""
        from app.events.models.details import MaintenanceDetail

        return set(
            AssetEvent.objects.filter(asset_id=asset_id).values_list("event_id", flat=True)
        ) | set(
            MaintenanceDetail.objects.filter(asset_id=asset_id).values_list("pk", flat=True)
        )
