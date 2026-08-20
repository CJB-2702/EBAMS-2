from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class DispatchSkill(AuditFieldsMixin):
    """Dispatching-owned catalogue of operating qualifications — CDL class,
    radio operator, site access level. Distinct from maintenance competence,
    which the system does not catalogue.

    Keeps requires_expiry: asset capability expiry was cut (design_drift.md
    §2.11), but user skill expiry is a different and real fact, and stays.
    """

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    description = models.TextField(blank=True)
    requires_expiry = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "dispatch_skill"
        ordering = ["name"]
        permissions = [
            ("skills_catalogue", "Can manage the skills catalogue"),
        ]

    def __str__(self) -> str:
        return self.name
