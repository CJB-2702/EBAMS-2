from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.dispatching.models.abstract_mixins import AbstractModificationRequirement


class DispatchTemplateRequestedModification(AbstractModificationRequirement, AuditFieldsMixin):
    revision = models.ForeignKey(
        "dispatching.DispatchTemplateRevision",
        on_delete=models.CASCADE,
        related_name="requested_modifications",
    )

    class Meta:
        db_table = "dispatch_template_requested_modification"
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "defined_modification"],
                name="uq_dispatch_template_requested_modification",
            ),
        ]

    def __str__(self) -> str:
        return f"Revision #{self.revision_id} requires modification {self.defined_modification_id}"
