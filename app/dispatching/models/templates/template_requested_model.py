from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.dispatching.models.abstract_mixins import AbstractModelRequirement


class DispatchTemplateRequestedModel(AbstractModelRequirement, AuditFieldsMixin):
    revision = models.ForeignKey(
        "dispatching.DispatchTemplateRevision",
        on_delete=models.CASCADE,
        related_name="requested_models",
    )

    class Meta:
        db_table = "dispatch_template_requested_model"
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "model", "configuration_template"],
                name="uq_dispatch_template_requested_model",
            ),
            # SQL NULL != NULL, so the composite constraint above alone
            # would let two unconfigured rows for the same model coexist.
            models.UniqueConstraint(
                fields=["revision", "model"],
                condition=models.Q(configuration_template__isnull=True),
                name="uq_dispatch_template_requested_model_unconfigured",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="dispatch_template_requested_model_quantity_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"Revision #{self.revision_id} requires model {self.model_id}"
