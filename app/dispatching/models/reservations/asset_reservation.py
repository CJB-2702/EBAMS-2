from django.db import models

from app.dispatching.models.enums import (
    ConditionRating,
    ReservationStatus,
    ReservationType,
)
from app.events.models.event import Event, EventType


class AssetReservation(Event):
    """One asset, one window of time, one accountable person. Standalone —
    the dispatch link is optional (dispatching_starter_kit/3_asset_reservations.md
    §2). Own domain, own status, own event — inherited from Event via MTI,
    exactly parallel to the dispatch itself (D1 in build_phase_1_models.md).

    AssetReservation.reservation_status is deliberately a separate field from
    Event.status (a plain "status" field would collide with Event's via MTI
    field-name uniqueness anyway): the reservation lifecycle (Tentative ->
    Confirmed -> CheckedOut -> Returned, plus Cancelled and NoShow) is not the
    Event vocabulary.
    """

    reservation_status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.TENTATIVE,
    )
    reservation_type = models.CharField(
        max_length=20,
        choices=ReservationType.choices,
    )

    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    dispatch = models.ForeignKey(
        "events.DispatchingDetail",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    accountable_person = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="accountable_reservations",
    )

    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    origin = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)

    # ── Dispatcher-recorded handover track — authoritative ───────────────────
    condition_out = models.CharField(max_length=20, choices=ConditionRating.choices, blank=True)
    condition_in = models.CharField(max_length=20, choices=ConditionRating.choices, blank=True)
    physical_checkout_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the asset physically left — not when paperwork was done.",
    )
    physical_checkin_at = models.DateTimeField(null=True, blank=True)
    dispatcher_checkout_notes = models.TextField(blank=True)
    dispatcher_checkin_notes = models.TextField(blank=True)
    checkout_verified_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_checkout_verified",
    )
    checkout_verified_at = models.DateTimeField(null=True, blank=True)
    return_verified_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_return_verified",
    )
    return_verified_at = models.DateTimeField(null=True, blank=True)

    # ── User-reported handover track — self-service, never overwrites the
    # dispatcher track ────────────────────────────────────────────────────────
    user_reported_condition_out = models.CharField(max_length=20, choices=ConditionRating.choices, blank=True)
    user_reported_condition_in = models.CharField(max_length=20, choices=ConditionRating.choices, blank=True)
    user_checkout_submitted_at = models.DateTimeField(null=True, blank=True)
    user_checkin_submitted_at = models.DateTimeField(null=True, blank=True)
    user_checkout_notes = models.TextField(blank=True)
    user_checkin_notes = models.TextField(blank=True)
    user_checked_out_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_user_checked_out",
    )
    user_checked_in_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_user_checked_in",
    )

    # ── User-reported meters — reference information, NOT a meter reading ───
    # The one place dispatching stores a meter number on its own table, and it
    # is deliberate: these are what the person at the vehicle said they saw.
    # They are never written to MeterHistory, never update Asset.meterN, and
    # must never be treated as the asset's reading — only the dispatcher track
    # below does that, via MeterReadRecorder. Keeping the user's number beside
    # the official one is the whole point: a discrepancy between them is a
    # finding, and syncing these into the asset would destroy it.
    # See dispatching_starter_kit/3_asset_reservations.md §7.2-7.3.
    user_meter1_out = models.FloatField(
        null=True, blank=True,
        help_text="Meter one as reported by the user at checkout. Informational only.",
    )
    user_meter2_out = models.FloatField(
        null=True, blank=True,
        help_text="Meter two as reported by the user at checkout. Informational only.",
    )
    user_meter1_in = models.FloatField(
        null=True, blank=True,
        help_text="Meter one as reported by the user at return. Informational only.",
    )
    user_meter2_in = models.FloatField(
        null=True, blank=True,
        help_text="Meter two as reported by the user at return. Informational only.",
    )

    # ── Meters — two references into the asset's own meter history, never
    # stored numbers (dispatching_starter_kit/3_asset_reservations.md §7.3) ───
    initial_meter_read = models.ForeignKey(
        "assets.MeterHistory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_as_initial",
    )
    final_meter_read = models.ForeignKey(
        "assets.MeterHistory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_as_final",
    )

    # ── Conflict override — a confirmed booking overlapping another confirmed
    # one is blocked unless explicitly acknowledged (§10) ────────────────────
    conflict_acknowledged_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_conflict_acknowledged",
    )
    conflict_acknowledged_at = models.DateTimeField(null=True, blank=True)
    conflict_acknowledgement_reason = models.TextField(blank=True)

    # ── Cancellation ───────────────────────────────────────────────────────
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_cancelled",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "asset_reservation"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(scheduled_start__lte=models.F("scheduled_end")),
                name="reservation_scheduled_window_ordered",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(physical_checkout_at__isnull=True)
                    | models.Q(physical_checkin_at__isnull=True)
                    | models.Q(physical_checkout_at__lte=models.F("physical_checkin_at"))
                ),
                name="reservation_dispatcher_handover_ordered",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(user_checkout_submitted_at__isnull=True)
                    | models.Q(user_checkin_submitted_at__isnull=True)
                    | models.Q(user_checkout_submitted_at__lte=models.F("user_checkin_submitted_at"))
                ),
                name="reservation_user_handover_ordered",
            ),
        ]
        permissions = [
            ("reservation_book", "Can create tentative bookings, cancel own tentative bookings"),
            ("reservation_confirm", "Can promote tentative to confirmed, cancel confirmed bookings, acknowledge conflicts"),
            ("reservation_self_service", "Can checkout and return as the accountable person"),
            ("reservation_verify", "Can perform dispatcher-side handover and return verification"),
            ("reservation_maintenance_hold", "Can create and release maintenance-type bookings only"),
        ]

    def save(self, *args, **kwargs) -> None:
        self.event_type = EventType.RESERVATION
        super().save(*args, **kwargs)
