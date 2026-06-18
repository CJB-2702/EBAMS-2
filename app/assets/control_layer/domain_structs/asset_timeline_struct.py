"""AssetTimelineStruct — read model for an asset's event history (its story).

Clusters every ``AssetEvent`` link for one asset together with its resolved
``Event`` row, ordered newest-first and grouped by ``role`` (lifecycle,
capability, configuration, …). The narration was already written at create time
by ``AssetEventNarrator``; this struct only gathers and orders it for a page.

Read-only; ``to_dict()`` for rendering a timeline panel.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.models.core.asset_event import AssetEvent

if TYPE_CHECKING:
    from app.assets.models import Asset


class AssetTimelineStruct:
    """Read model for an asset's chronological event timeline."""

    UNROLED = "general"  # bucket key for links whose role is null/blank

    def __init__(self, asset: "Asset", links: list[AssetEvent]) -> None:
        self.asset = asset
        # AssetEvent rows with their Event eager-loaded, newest event first.
        self.links = links

    @classmethod
    def from_asset(cls, asset: "Asset", *, limit: int | None = None) -> "AssetTimelineStruct":
        link_qs = (
            AssetEvent.objects.filter(asset=asset)
            .select_related("event")
            .order_by("-event__created_at", "-id")
        )
        if limit is not None:
            link_qs = link_qs[:limit]
        return cls(asset=asset, links=list(link_qs))

    @classmethod
    def from_id(cls, asset_id: int, *, limit: int | None = None) -> "AssetTimelineStruct | None":
        from app.assets.models import Asset

        asset = Asset.objects.filter(id=asset_id).first()
        if asset is None:
            return None
        return cls.from_asset(asset, limit=limit)

    # ── Grouping ─────────────────────────────────────────────────────────────

    def by_role(self) -> dict[str, list[AssetEvent]]:
        """Links grouped by role, preserving newest-first order within each."""
        grouped: dict[str, list[AssetEvent]] = {}
        for link in self.links:
            grouped.setdefault(link.role or self.UNROLED, []).append(link)
        return grouped

    # ── Serialization ────────────────────────────────────────────────────────

    @staticmethod
    def _entry(link: AssetEvent) -> dict:
        event = link.event
        return {
            "asset_event_id": link.id,
            "role": link.role or AssetTimelineStruct.UNROLED,
            "event_id": event.id,
            "title": event.title,
            "description": event.description,
            "event_type": event.event_type,
            "status": event.status,
            "created_at": event.created_at,
        }

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset.id,
            "count": len(self.links),
            "entries": [self._entry(link) for link in self.links],
            "by_role": {
                role: [self._entry(link) for link in links]
                for role, links in self.by_role().items()
            },
        }
