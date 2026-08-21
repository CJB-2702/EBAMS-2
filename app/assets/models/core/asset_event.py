"""AssetEvent re-export for backwards compatibility.

AssetEvent is owned by the events sub-application (app.events.models.AssetEvent).
"""

from app.events.models.asset_event import AssetEvent

__all__ = ["AssetEvent"]
