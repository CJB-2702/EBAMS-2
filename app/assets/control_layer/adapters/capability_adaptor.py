"""Adaptors mapping capability HTTP POST payloads to structured write input.

All boundary coercion lives here: ``getlist`` for multi-value sets, checkbox→bool,
blank→None, ids→int. The per-row qty/notes/active editors key their inputs by the
target id (``qty_<id>``, ``notes_<id>``, ``active_<id>``); these adaptors fold them
back into a list of per-target dicts.
"""

from __future__ import annotations


class CapabilityDefinitionCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "name": (post.get("name") or "").strip(),
            "code": (post.get("code") or "").strip().upper(),
            "description": (post.get("description") or "").strip() or None,
            "is_active": _checkbox(post, "is_active"),
        }


class CapabilityDefinitionEditAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        data = CapabilityDefinitionCreateAdaptor.from_post(post)
        data["assigned_class_ids"] = _int_list(post, "assigned_classes")
        data["assigned_model_ids"] = _int_list(post, "assigned_models")
        return data


class AssetCapabilitiesEditAdaptor:
    """One asset's direct capability set: ``capabilities`` ids + per-id fields."""

    @staticmethod
    def from_post(post) -> list[dict]:
        rows: list[dict] = []
        for def_id in _int_list(post, "capabilities"):
            rows.append(
                {
                    "definition_id": def_id,
                    "qty": _int_or_none(post.get(f"qty_{def_id}")),
                    "notes": (post.get(f"notes_{def_id}") or "").strip() or None,
                    "is_active": _checkbox(post, f"active_{def_id}"),
                }
            )
        return rows


class AssetBulkManagementAdaptor:
    """One definition across many assets: ``assigned_assets`` ids + per-id fields."""

    @staticmethod
    def from_post(post) -> list[dict]:
        rows: list[dict] = []
        for asset_id in _int_list(post, "assigned_assets"):
            rows.append(
                {
                    "asset_id": asset_id,
                    "qty": _int_or_none(post.get(f"qty_{asset_id}")),
                    "notes": (post.get(f"notes_{asset_id}") or "").strip() or None,
                    "is_active": _checkbox(post, f"active_{asset_id}"),
                }
            )
        return rows


def _checkbox(post, key: str) -> bool:
    return post.get(key) in ("on", "true", "True", "1")


def _int_or_none(raw) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _int_list(post, key: str) -> list[int]:
    out: list[int] = []
    for raw in post.getlist(key):
        try:
            out.append(int(raw))
        except (TypeError, ValueError):
            continue
    return out
