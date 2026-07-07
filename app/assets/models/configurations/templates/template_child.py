from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class TemplateChild(AuditFieldsMixin):
    """Declares an expected child asset (by model) within a configuration template."""

    parent_template = models.ForeignKey(
        "assets.ConfigurationTemplate",
        on_delete=models.CASCADE,
        related_name="child_declarations",
    )
    child_model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.PROTECT,
        related_name="template_child_declarations",
    )
    quantity = models.PositiveSmallIntegerField(default=1)
    is_required = models.BooleanField(default=False)

    # INTERIM (tech debt: "Template child configuration reference"): a soft pointer
    # to the ConfigurationTemplate the child should be built to, stored as the
    # template NAME (free string), not a FK. Avoids the cycle/DAG recursion the real
    # child_template FK would introduce. Optional. Do not build integrity-critical
    # logic on this — see docs/technical_decisions/tech_debt.
    child_configuration = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = "template_child"

    def __str__(self) -> str:
        return f"TemplateChild parent={self.parent_template_id} child_model={self.child_model_id} qty={self.quantity}"
