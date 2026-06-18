from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class ModificationModel(AuditFieldsMixin):
    """One allowed asset model for a DefinedModification.

    Always author-maintained. Binding in STRICT and MODEL_SET modes; a non-binding
    search hint in CLASS_ONLY and UNRESTRICTED. In STRICT mode a model whose parent
    class is absent from the class allow-list is rejected at author time (the
    dead-model guard) — it could never pass the AND combine. See the kit matrix.
    """

    defined_modification = models.ForeignKey(
        "assets.DefinedModification",
        on_delete=models.CASCADE,
        related_name="model_allowlist",
    )
    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = "modification_model"
        constraints = [
            models.UniqueConstraint(
                fields=["defined_modification", "model"],
                name="uq_modification_model",
            ),
        ]

    def __str__(self) -> str:
        return f"ModificationModel {self.defined_modification_id}↔{self.model_id}"
