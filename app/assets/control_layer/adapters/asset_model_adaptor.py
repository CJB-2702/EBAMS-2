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
            "subtype_name": (post.get("subtype_name") or "").strip() or None,
            "revision": (post.get("revision") or "").strip() or None,
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
