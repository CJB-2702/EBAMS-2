"""PartCreateAdaptor — HTTP POST payload -> PartFactory input dict."""

from __future__ import annotations

from app.parts.control_layer.adapters.form_parsing import parse_checkbox


class PartCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "part_number": (post.get("part_number") or "").strip(),
            "name": (post.get("name") or "").strip(),
            "description": (post.get("description") or "").strip(),
            "part_type": (post.get("part_type") or "").strip(),
            "category": (post.get("category") or "").strip(),
            "is_active": parse_checkbox(post, "is_active"),
            "is_domain_limited": parse_checkbox(post, "is_domain_limited"),
        }
