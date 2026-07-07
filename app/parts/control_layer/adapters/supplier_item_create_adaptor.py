from __future__ import annotations


class SupplierItemCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "part_manufacturer_id": _to_int(post.get("part_manufacturer_id")),
            "internal_part_id": _to_int(post.get("internal_part_id")),
            "manufacturer_part_number": (post.get("manufacturer_part_number") or "").strip(),
            "name": (post.get("name") or "").strip(),
            "description": (post.get("description") or "").strip(),
            "is_active": post.get("is_active") in ("on", "true", "True", "1"),
            "min_major_revision_number": _to_int(post.get("min_major_revision_number")),
            "min_minor_revision_number": _to_int(post.get("min_minor_revision_number")),
            "max_major_revision_number": _to_int(post.get("max_major_revision_number")),
            "max_minor_revision_number": _to_int(post.get("max_minor_revision_number")),
        }


class VendorRevisionRecordAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "vendor_revision_id": (post.get("vendor_revision_id") or "").strip(),
            "note": (post.get("note") or "").strip(),
        }


def _to_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
