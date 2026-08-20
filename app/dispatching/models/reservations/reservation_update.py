from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.dispatching.models.enums import ReservationUpdateChangeType


class ReservationUpdate(AuditFieldsMixin):
    """One row per change to a reservation — reschedules, asset swaps, status
    transitions, cancellations, extensions. Deliberately separate from
    comments: a reschedule is a fact (old window, new window, who, when, why),
    not prose. Append-only, same shape and reasoning as
    procurement.PartDemandUpdate — never updated, never deleted, hence
    AuditFieldsMixin without SoftDeleteMixin.

    See dispatching_starter_kit/3_asset_reservations.md §8.
    """

    reservation = models.ForeignKey(
        "dispatching.AssetReservation",
        on_delete=models.CASCADE,
        related_name="updates",
    )
    change_type = models.CharField(
        max_length=20,
        choices=ReservationUpdateChangeType.choices,
    )
    field_changed = models.CharField(max_length=100, blank=True)
    previous_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    reason = models.TextField(blank=True)

    # Nullable for system-generated transitions with no human actor.
    actor = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="reservation_updates",
        null=True,
        blank=True,
    )
    is_system_generated = models.BooleanField(default=False)

    class Meta:
        db_table = "reservation_update"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["reservation", "created_at"], name="ru_reservation_created_idx"),
            models.Index(fields=["change_type"], name="ru_change_type_idx"),
        ]

    def __str__(self) -> str:
        return f"Reservation #{self.reservation_id} {self.change_type}"
