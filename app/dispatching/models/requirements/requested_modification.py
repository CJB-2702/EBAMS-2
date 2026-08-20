from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.dispatching.models.abstract_mixins import AbstractModificationRequirement


class DispatchRequestedModification(AbstractModificationRequirement, AuditFieldsMixin):
    dispatch = models.ForeignKey(
        "events.DispatchingDetail",
        on_delete=models.CASCADE,
        related_name="requested_modifications",
    )

    class Meta:
        db_table = "dispatch_requested_modification"
        constraints = [
            models.UniqueConstraint(
                fields=["dispatch", "defined_modification"],
                name="uq_dispatch_requested_modification",
            ),
        ]

    def __str__(self) -> str:
        return f"Dispatch #{self.dispatch_id} requires modification {self.defined_modification_id}"
