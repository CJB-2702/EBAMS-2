"""AssetThreeSixtyStruct — the whole asset detail page in one read model.

Composes the smaller per-area structs (base, capabilities, configuration,
hierarchy, timeline) into a single object the 360 detail view can build once and
hand to the template. Each slice stays independently usable; this struct just
gathers them so the view does one call instead of orchestrating five.

**Deliberately does NOT include extensions.** The assets app stays ignorant of
``detail_extensions`` (kit D7/D8): the 360 page pulls extension cards over HTMX
from ``/detail_extensions/<asset_id>/?format=htmx-panel`` — never by importing an
extension struct here. Keeping that import out of this file is what preserves the
one-way dependency.

Read-only; ``to_dict()`` merges the slices for rendering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.control_layer.domain_structs.asset_capability_struct import (
    AssetCapabilityStruct,
)
from app.assets.control_layer.domain_structs.asset_configuration_struct import (
    AssetConfigurationStruct,
)
from app.assets.control_layer.domain_structs.asset_hierarchy_struct import (
    AssetHierarchyStruct,
)
from app.assets.control_layer.domain_structs.asset_struct import AssetStruct
from app.assets.control_layer.domain_structs.asset_timeline_struct import (
    AssetTimelineStruct,
)

if TYPE_CHECKING:
    from app.assets.models import Asset


class AssetThreeSixtyStruct:
    """Aggregate read model for the asset 360 detail page."""

    #: Default number of timeline entries loaded for the detail page.
    TIMELINE_LIMIT = 25

    def __init__(
        self,
        base: AssetStruct,
        capabilities: AssetCapabilityStruct,
        configuration: AssetConfigurationStruct,
        hierarchy: AssetHierarchyStruct,
        timeline: AssetTimelineStruct,
    ) -> None:
        self.base = base
        self.capabilities = capabilities
        self.configuration = configuration
        self.hierarchy = hierarchy
        self.timeline = timeline

    @property
    def asset(self) -> "Asset":
        return self.base.asset

    @classmethod
    def from_asset(
        cls,
        asset: "Asset",
        *,
        timeline_limit: int | None = TIMELINE_LIMIT,
    ) -> "AssetThreeSixtyStruct":
        return cls(
            base=AssetStruct.from_instance(asset),
            capabilities=AssetCapabilityStruct.from_asset(asset),
            configuration=AssetConfigurationStruct.from_asset(asset),
            hierarchy=AssetHierarchyStruct.from_asset(asset),
            timeline=AssetTimelineStruct.from_asset(asset, limit=timeline_limit),
        )

    @classmethod
    def from_id(
        cls,
        asset_id: int,
        *,
        eager: bool = True,
        timeline_limit: int | None = TIMELINE_LIMIT,
    ) -> "AssetThreeSixtyStruct":
        # AssetStruct guarantees existence (raises AssetNotFoundError) and can
        # eager-load the FK slices the detail header needs.
        base = AssetStruct(asset_id, eager=eager)
        return cls.from_asset(base.asset, timeline_limit=timeline_limit)

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "asset": self.base.to_dict(),
            "capabilities": self.capabilities.to_dict(),
            "configuration": self.configuration.to_dict(),
            "hierarchy": self.hierarchy.to_dict(),
            "timeline": self.timeline.to_dict(),
            # Extensions are intentionally absent — loaded by the template via the
            # detail_extensions HTMX panel URL, not composed here (dependency rule).
        }
