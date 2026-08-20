from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.dispatching.models.abstract_mixins import AbstractCapabilityRequirement


class DispatchRequestedCapability(AbstractCapabilityRequirement, AuditFieldsMixin):
    dispatch = models.ForeignKey(
        "events.DispatchingDetail",
        on_delete=models.CASCADE,
        related_name="requested_capabilities",
    )

    class Meta:
        db_table = "dispatch_requested_capability"
        constraints = [
            models.UniqueConstraint(
                fields=["dispatch", "capability_definition"],
                name="uq_dispatch_requested_capability",
            ),
        ]

    def __str__(self) -> str:
        return f"Dispatch #{self.dispatch_id} requires capability {self.capability_definition_id}"
