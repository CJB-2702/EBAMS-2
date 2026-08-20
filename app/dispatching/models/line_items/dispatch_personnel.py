from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.dispatching.models.enums import PersonnelRole


class DispatchPersonnel(AuditFieldsMixin):
    """Crew roster. FK to the dispatch, never to a reservation — three people
    and two vehicles belong to neither vehicle
    (dispatching_starter_kit/3_asset_reservations.md §11)."""

    dispatch = models.ForeignKey(
        "events.DispatchingDetail",
        on_delete=models.CASCADE,
        related_name="crew",
    )
    user = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="dispatch_assignments",
    )
    role = models.CharField(
        max_length=20,
        choices=PersonnelRole.choices,
        default=PersonnelRole.PASSENGER,
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "dispatch_personnel"
        constraints = [
            models.UniqueConstraint(
                fields=["dispatch", "user"],
                name="uq_dispatch_personnel_dispatch_user",
            ),
        ]

    def __str__(self) -> str:
        return f"Dispatch #{self.dispatch_id} crew: {self.user_id}"
