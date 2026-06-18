"""AssetCreateAdaptor — maps an HTTP POST payload to AssetFactory input.

Type conversion (strings → ints) happens here at the boundary, never on the
model or in the factory.
"""

from __future__ import annotations


class AssetCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "name": (post.get("name") or "").strip(),
            "serial_number": (post.get("serial_number") or "").strip(),
            "domain_id": _to_int(post.get("domain_id")),
            "model_id": _to_int(post.get("model_id")),
            "status": post.get("status") or "Active",
            "parent_asset_id": _to_int(post.get("parent_asset_id")),
        }


def _to_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
