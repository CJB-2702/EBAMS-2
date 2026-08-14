from __future__ import annotations

_TRUTHY = ("on", "true", "True", "1")


class VendorCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "name": (post.get("name") or "").strip(),
            "code": (post.get("code") or "").strip() or None,
            "website": (post.get("website") or "").strip() or None,
            "is_active": post.get("is_active") in _TRUTHY,
        }

    @staticmethod
    def from_quick_create_post(post) -> dict:
        # qc_-prefixed because this sub-form lives inside the price grid's
        # single outer <form>, alongside the grid's own fields.
        return {
            "name": (post.get("qc_name") or "").strip(),
            "code": None,
            "website": None,
            "is_active": post.get("qc_is_active") in _TRUTHY,
        }
