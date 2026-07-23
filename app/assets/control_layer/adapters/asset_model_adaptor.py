"""AssetModelCreateAdaptor / AssetModelEditAdaptor — map an HTTP POST payload to
AssetModel write input.

The create form exposes identity, asset class, manufacturers, and meter units; the
edit form adds the declared capability set. Type coercion (ids → int, blank →
``None``) happens here at the boundary. The form does not expose the revision tree,
so created models are always base models.
"""

from __future__ import annotations

_METER_FIELDS = ("meter1_unit", "meter2_unit", "meter3_unit", "meter4_unit")


class AssetModelCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        manufacturer_ids = _int_list(post, "manufacturers")
        data = {
            "model_name": (post.get("model_name") or "").strip(),
            "version": (post.get("version") or "").strip(),
            "version_rank": _to_int(post.get("version_rank")),
            "config_baselines": _csv_list(post, "config_baselines"),
            "is_base_model": True,
            "base_model_id": None,
            "asset_class_id": _to_int(post.get("asset_class")),
            "manufacturer_ids": manufacturer_ids,
            "primary_manufacturer_id": manufacturer_ids[0] if manufacturer_ids else None,
        }
        for field in _METER_FIELDS:
            data[field] = (post.get(field) or "").strip() or None
        return data


class AssetModelEditAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        data = AssetModelCreateAdaptor.from_post(post)
        # Identity uniqueness (base/revision) is not re-keyed on edit here; the
        # edit form keeps the model a base model.
        data.pop("is_base_model", None)
        data.pop("base_model_id", None)
        # Manufacturers are managed on the edit page by the live HTMX dual-listbox
        # (see model_move_manufacturers), not the main form submit — so drop them
        # here to avoid the empty POST wiping the linked set.
        data.pop("manufacturer_ids", None)
        data.pop("primary_manufacturer_id", None)
        data["assigned_capability_ids"] = _int_list(post, "assigned_capabilities")
        return data


def _to_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_list(post, key: str) -> list[int]:
    out: list[int] = []
    for raw in post.getlist(key):
        parsed = _to_int(raw)
        if parsed is not None:
            out.append(parsed)
    return out


def _csv_list(post, key: str) -> list[str]:
    """Normalize a repeated (``getlist``) or comma-separated field into a trimmed,
    de-duped (case-insensitive), non-empty list preserving first-seen order.

    The model form posts one hidden input per chip via <tag-list-editor>, so we read
    ``getlist`` first; each entry is still comma-split as a safety net for pasted or
    legacy single-field values."""
    raw_values = post.getlist(key) if hasattr(post, "getlist") else [post.get(key) or ""]
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_values:
        for part in (raw or "").split(","):
            value = part.strip()
            if value and value.lower() not in seen:
                seen.add(value.lower())
                out.append(value)
    return out
