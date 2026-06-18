from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class TemplateModification(AuditFieldsMixin):
    """Junction: a DefinedModification expected inside a ConfigurationTemplate."""

    template = models.ForeignKey(
        "assets.ConfigurationTemplate",
        on_delete=models.CASCADE,
        related_name="modification_links",
    )
    defined_modification = models.ForeignKey(
        "assets.DefinedModification",
        on_delete=models.PROTECT,
        related_name="template_links",
    )
    context_notes = models.TextField(null=True, blank=True)
    is_required = models.BooleanField(default=False)

    class Meta:
        db_table = "template_modification"
        constraints = [
            models.UniqueConstraint(
                fields=["template", "defined_modification"],
                name="uq_template_modification",
            ),
        ]

    def __str__(self) -> str:
        return f"TemplateModification {self.template_id}↔{self.defined_modification_id}"
