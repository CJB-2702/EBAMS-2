"""ManufacturerCreateAdaptor / ManufacturerEditAdaptor — map an HTTP POST
payload to manufacturer write input.

Type coercion (checkbox → bool, blank → ``None``) happens here at the boundary,
never on the model or in the factory/context. The edit adaptor only includes
keys actually present in the payload so an edit touches just submitted fields.
"""

from __future__ import annotations


class ManufacturerCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "name": (post.get("name") or "").strip(),
            "code": (post.get("code") or "").strip() or None,
            "website": (post.get("website") or "").strip() or None,
            "is_active": _checkbox(post, "is_active"),
        }


class ManufacturerEditAdaptor:
    EDITABLE = ("name", "code", "website")

    @classmethod
    def from_post(cls, post) -> dict:
        data: dict = {}
        for field in cls.EDITABLE:
            if field in post:
                data[field] = (post.get(field) or "").strip() or (
                    "" if field == "name" else None
                )
        # A checkbox absent from the payload means unchecked, so is_active is
        # always derivable on an edit submit.
        data["is_active"] = _checkbox(post, "is_active")
        return data


def _checkbox(post, key: str) -> bool:
    return post.get(key) in ("on", "true", "True", "1")
