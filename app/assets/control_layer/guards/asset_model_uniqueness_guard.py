"""Guard type: Validator.

Guards AssetModel uniqueness and base/revision consistency: the natural key
``(model_name, version)`` must be unique, and the base-model flag must agree with
the presence of a base_model link. ``config_baselines`` is an allow-list, not part
of identity, so it plays no role here. This validator front-runs the DB-level
``uq_assetmodel_identity`` constraint to produce a friendly, case-insensitive
message before the database rejects.
"""

from __future__ import annotations

from app.assets.models import AssetModel


class AssetModelUniquenessValidator:
    """Validates duplicate detection and base/revision consistency."""

    @classmethod
    def validate(
        cls,
        *,
        model_name: str,
        version: str | None,
        is_base_model: bool,
        base_model_id: int | None,
        exclude_model_id: int | None = None,
    ) -> list[str]:
        errors: list[str] = []

        if not (model_name or "").strip():
            errors.append("Model name is required.")

        qs = AssetModel.objects.filter(
            model_name__iexact=model_name,
            version__iexact=version or "",
        )
        if exclude_model_id is not None:
            qs = qs.exclude(id=exclude_model_id)
        if qs.exists():
            errors.append(
                f"A model with name '{model_name}' and version '{version or ''}' "
                f"already exists."
            )

        # A base model has no base_model link; a revision must have one.
        if is_base_model and base_model_id is not None:
            errors.append("A base model cannot reference a base_model.")
        if not is_base_model and base_model_id is None:
            errors.append("A revision must reference a base_model.")

        return errors
