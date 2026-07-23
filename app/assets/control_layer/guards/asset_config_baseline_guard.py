"""Guard type: Validator (advisory).

Soft, non-blocking check that an Asset's declared ``config_baseline`` is one of the
values in its model's ``config_baselines`` allow-list. The real constraint is the UI
dropdown (see ``Asset.config_baseline``); this guard only covers paths the dropdown
cannot — API / import / F5 fallback — and it NEVER raises or blocks. It returns
warning strings the caller may surface via ``messages.warning`` if it chooses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.assets.models import AssetModel


class AssetConfigBaselineValidator:
    """Advisory-only: warns when a baseline is off the model's allow-list."""

    @classmethod
    def check(cls, *, value: str | None, model: "AssetModel") -> list[str]:
        value = (value or "").strip()
        if not value:
            return []
        accepted = {str(v).strip().lower() for v in (model.config_baselines or [])}
        if value.lower() in accepted:
            return []
        return [
            f"'{value}' is not a known config baseline for {model}. "
            f"Saved anyway — add it to the model to make it a standard option."
        ]
