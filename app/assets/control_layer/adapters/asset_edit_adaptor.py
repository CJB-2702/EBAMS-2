"""AssetEditAdaptor — maps an HTTP POST payload to asset-edit input.

Only includes keys actually present in the payload, so an edit touches just the
submitted fields.
"""

from __future__ import annotations


class AssetEditAdaptor:
    EDITABLE = ("name", "serial_number", "status")

    @classmethod
    def from_post(cls, post) -> dict:
        data: dict = {}
        for field in cls.EDITABLE:
            if field in post:
                data[field] = (post.get(field) or "").strip()
        if "parent_asset_id" in post:
            value = post.get("parent_asset_id")
            data["parent_asset_id"] = int(value) if value not in (None, "") else None
        return data
