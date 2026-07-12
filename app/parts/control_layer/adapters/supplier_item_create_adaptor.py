from __future__ import annotations

from app.parts.control_layer.adapters.form_parsing import parse_checkbox, parse_int


class SupplierItemCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "part_manufacturer_id": parse_int(post.get("part_manufacturer_id")),
            "internal_part_id": parse_int(post.get("internal_part_id")),
            "manufacturer_part_number": (post.get("manufacturer_part_number") or "").strip(),
            "name": (post.get("name") or "").strip(),
            "description": (post.get("description") or "").strip(),
            # No "active" toggle is exposed on the create form (v1) — a supplier item is active
            # by default (matches the model's own default), so an absent key must mean True, not
            # False. Only an explicit falsy value turns it off.
            "is_active": parse_checkbox(post, "is_active") if "is_active" in post else True,
            "min_major_revision_number": parse_int(post.get("min_major_revision_number")),
            "min_minor_revision_number": parse_int(post.get("min_minor_revision_number")),
            "max_major_revision_number": parse_int(post.get("max_major_revision_number")),
            "max_minor_revision_number": parse_int(post.get("max_minor_revision_number")),
        }


class VendorRevisionRecordAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "vendor_revision_id": (post.get("vendor_revision_id") or "").strip(),
            "note": (post.get("note") or "").strip(),
        }
