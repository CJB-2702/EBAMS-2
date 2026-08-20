from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.dispatching.models.abstract_mixins import AbstractCapabilityRequirement


class DispatchTemplateRequestedCapability(AbstractCapabilityRequirement, AuditFieldsMixin):
    revision = models.ForeignKey(
        "dispatching.DispatchTemplateRevision",
        on_delete=models.CASCADE,
        related_name="requested_capabilities",
    )

    class Meta:
        db_table = "dispatch_template_requested_capability"
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "capability_definition"],
                name="uq_dispatch_template_requested_capability",
            ),
        ]

    def __str__(self) -> str:
        return f"Revision #{self.revision_id} requires capability {self.capability_definition_id}"
