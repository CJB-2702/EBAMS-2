"""Adaptor: raw POST QueryDicts from the warehouse/room designer forms into
plain dicts the `TopographyContext` verbs accept.

Entrypoints never hand a `request.POST` to the control layer directly — this
is the one place form-field names are known, so renaming an input is a
one-file change and the context keeps a typed keyword signature.
"""

from __future__ import annotations


class WarehouseFormAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "name": (post.get("name") or "").strip(),
            "code": (post.get("code") or "").strip(),
            "division_id": (post.get("division_id") or "").strip() or None,
            "address": (post.get("address") or "").strip(),
            "domain_ids": [d for d in post.getlist("domain_ids") if d],
        }


class RoomFormAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "room_name": (post.get("room_name") or "").strip(),
            "description": (post.get("description") or "").strip(),
            "excluded_domain_ids": [
                d for d in post.getlist("excluded_domain_ids") if d
            ],
        }


class RoomLocationFormAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        """Accepts either the two-field coordinate pair or a single hyphenated
        `display_code` typed into one box — the legacy designer's "Location ID"
        field was free text like `3-1`, and operators still type it that way."""
        major = (post.get("major_coord") or "").strip()
        minor = (post.get("minor_coord") or "").strip()
        if not major and not minor:
            combined = (post.get("display_code") or "").strip()
            if "-" in combined:
                major, minor = combined.split("-", 1)
                major, minor = major.strip(), minor.strip()
            else:
                major = combined
        return {"major_coord": major, "minor_coord": minor}


class StorageLocationFormAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {"atomic_coord": (post.get("atomic_coord") or "").strip()}
