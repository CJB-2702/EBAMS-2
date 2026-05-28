from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class ModelDetailTableTemplate(AuditFieldsMixin):
    """Declares which model-detail subclasses are provisioned for a given AssetModel."""

    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.CASCADE,
        related_name="model_detail_templates",
    )
    detail_table_type = models.CharField(max_length=100)
    many_to_one = models.BooleanField(default=False)

    class Meta:
        db_table = "model_detail_table_template"
        constraints = [
            models.UniqueConstraint(
                fields=["model", "detail_table_type"],
                name="uq_model_detail_table_template",
            ),
        ]

    def __str__(self) -> str:
        return f"ModelDetailTableTemplate {self.model_id}:{self.detail_table_type}"
