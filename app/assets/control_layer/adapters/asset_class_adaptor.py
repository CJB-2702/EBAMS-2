"""AssetClassCreateAdaptor / AssetClassEditAdaptor — map an HTTP POST payload to
asset-class write input.

Multi-value fields (``domains``, ``assigned_capabilities``) are read with
``getlist`` and coerced to ``int`` here at the boundary. The edit adaptor adds the
desired capability set, which the context syncs.

Meter units live here (not on AssetModel): every model under a class shares
the same meter semantics, so the class is the boundary where the label is set.
"""

from __future__ import annotations

_METER_FIELDS = ("meter1_unit", "meter2_unit", "meter3_unit", "meter4_unit")


class AssetClassCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        data = {
            "name": (post.get("name") or "").strip(),
            "category": (post.get("category") or "").strip() or None,
            "description": (post.get("description") or "").strip() or None,
            "restrict_to_domain_set": _checkbox(post, "restrict_to_domain_set"),
            "domain_ids": _int_list(post, "domains"),
        }
        for field in _METER_FIELDS:
            data[field] = (post.get(field) or "").strip() or None
        return data


class AssetClassEditAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        data = AssetClassCreateAdaptor.from_post(post)
        data["assigned_capability_ids"] = _int_list(post, "assigned_capabilities")
        return data


def _checkbox(post, key: str) -> bool:
    return post.get(key) in ("on", "true", "True", "1")


def _int_list(post, key: str) -> list[int]:
    out: list[int] = []
    for raw in post.getlist(key):
        try:
            out.append(int(raw))
        except (TypeError, ValueError):
            continue
    return out
