from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class ModificationAssetClass(AuditFieldsMixin):
    """One allowed (or system-derived) asset class for a DefinedModification.

    Combine rule (see the kit matrix): in STRICT mode these rows are
    author-maintained and AND-combined with the model list. In MODEL_SET mode they
    are **system-derived** — the distinct parent classes of the modification's model
    allow-list, rewritten by ApplicabilitySyncHandler, never hand-authored. In
    CLASS_ONLY mode they are the binding gate; in UNRESTRICTED they are suggestions.
    """

    defined_modification = models.ForeignKey(
        "assets.DefinedModification",
        on_delete=models.CASCADE,
        related_name="class_allowlist",
    )
    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = "modification_asset_class"
        constraints = [
            models.UniqueConstraint(
                fields=["defined_modification", "asset_class"],
                name="uq_modification_asset_class",
            ),
        ]

    def __str__(self) -> str:
        return f"ModificationAssetClass {self.defined_modification_id}↔{self.asset_class_id}"
