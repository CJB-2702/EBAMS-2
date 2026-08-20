from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.dispatching.models.abstract_mixins import AbstractModelRequirement


class DispatchRequestedModel(AbstractModelRequirement, AuditFieldsMixin):
    dispatch = models.ForeignKey(
        "events.DispatchingDetail",
        on_delete=models.CASCADE,
        related_name="requested_models",
    )

    class Meta:
        db_table = "dispatch_requested_model"
        constraints = [
            models.UniqueConstraint(
                fields=["dispatch", "model", "configuration_template"],
                name="uq_dispatch_requested_model",
            ),
            # SQL NULL != NULL, so the composite constraint above alone
            # would let two unconfigured rows for the same model coexist.
            models.UniqueConstraint(
                fields=["dispatch", "model"],
                condition=models.Q(configuration_template__isnull=True),
                name="uq_dispatch_requested_model_unconfigured",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="dispatch_requested_model_quantity_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"Dispatch #{self.dispatch_id} requires model {self.model_id}"
