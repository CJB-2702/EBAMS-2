from __future__ import annotations

from app.parts.control_layer.adapters.form_parsing import parse_checkbox


class ManufacturerCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "name": (post.get("name") or "").strip(),
            "code": (post.get("code") or "").strip() or None,
            "website": (post.get("website") or "").strip() or None,
            "is_active": parse_checkbox(post, "is_active"),
        }

    @staticmethod
    def from_quick_create_post(post) -> dict:
        # qc_-prefixed because this sub-form lives inside the supplier-item wizard's single
        # outer <form>, alongside the wizard's own "name" field (item name) — unprefixed keys
        # would collide with that field on final submit.
        return {
            "name": (post.get("qc_name") or "").strip(),
            "code": (post.get("qc_code") or "").strip() or None,
            "website": (post.get("qc_website") or "").strip() or None,
            "is_active": parse_checkbox(post, "qc_is_active"),
        }
