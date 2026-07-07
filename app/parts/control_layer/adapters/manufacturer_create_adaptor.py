from __future__ import annotations


class ManufacturerCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "name": (post.get("name") or "").strip(),
            "code": (post.get("code") or "").strip() or None,
            "website": (post.get("website") or "").strip() or None,
            "is_active": post.get("is_active") in ("on", "true", "True", "1"),
        }
