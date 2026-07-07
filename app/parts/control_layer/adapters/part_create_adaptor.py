"""PartCreateAdaptor — HTTP POST payload -> PartFactory input dict."""

from __future__ import annotations


class PartCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "part_number": (post.get("part_number") or "").strip(),
            "name": (post.get("name") or "").strip(),
            "description": (post.get("description") or "").strip(),
            "part_type": (post.get("part_type") or "").strip(),
            "category": (post.get("category") or "").strip(),
            "is_active": _checkbox(post, "is_active"),
            "is_domain_limited": _checkbox(post, "is_domain_limited"),
        }


def _checkbox(post, key: str) -> bool:
    return post.get(key) in ("on", "true", "True", "1")
