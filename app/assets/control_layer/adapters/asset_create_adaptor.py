"""AssetCreateAdaptor — maps an HTTP POST payload to AssetFactory input.

Type conversion (strings → ints) happens here at the boundary, never on the
model or in the factory.
"""

from __future__ import annotations


class AssetCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        # The asset form names these fields ``domain`` / ``model`` /
        # ``parent_id``; map them to the factory's ``*_id`` keys here at the
        # boundary. ``asset_class`` from the form is ignored — the factory
        # denormalizes it from the chosen model.
        return {
            "name": (post.get("name") or "").strip(),
            "serial_number": (post.get("serial_number") or "").strip(),
            "domain_id": _to_int(post.get("domain") or post.get("domain_id")),
            "model_id": _to_int(post.get("model") or post.get("model_id")),
            "status": post.get("status") or "Active",
            "parent_asset_id": _to_int(post.get("parent_id") or post.get("parent_asset_id")),
            # Baseline of this unit + the "add new baseline…" escape from the dropdown.
            "config_baseline": (post.get("config_baseline") or "").strip() or None,
            "add_baseline_to_model": post.get("add_baseline_to_model") in ("1", "true", "on", "True"),
        }


def _to_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
