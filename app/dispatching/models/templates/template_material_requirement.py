from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class DispatchTemplateMaterialRequirement(AuditFieldsMixin):
    """A template holds part + quantity. NOT a demand link — instantiation is
    what raises the real, issuable demand (see
    dispatching.models.requirements.demand_link.DispatchDemandLink).
    Requested *parts* are requested material, in line with
    dispatching_starter_kit/2_dispatch.md §7 —
    see dispatching_starter_kit/1_dispatch_templates.md §6.4."""

    revision = models.ForeignKey(
        "dispatching.DispatchTemplateRevision",
        on_delete=models.CASCADE,
        related_name="material_requirements",
    )
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="dispatch_template_material_requirements",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "dispatch_template_material_requirement"
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "part"],
                name="uq_dispatch_template_material_requirement",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="dispatch_template_material_requirement_quantity_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"Revision #{self.revision_id} needs {self.quantity} x {self.part_id}"
