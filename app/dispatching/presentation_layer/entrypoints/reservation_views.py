"""Asset reservation screens — the booking surface
(dispatching_starter_kit/3_asset_reservations.md, 5_roles_and_permissions.md
§4.2).

The routes, and why they are split this way:

    /reservations                          list + calendar + summary
    /reservations/create                   pick an asset, state a window
    /reservation/<id>                      the hub — everything, read
    /reservation/<id>/lifecycle            POST only: confirm / cancel / no-show
    /reservation/<id>/user-checkout        \\
    /reservation/<id>/user-checkin          | one page per handover step
    /reservation/<id>/dispatcher-checkout   |
    /reservation/<id>/dispatcher-checkin   /
    /reservation/<id>/edit                 every field, dispatch managers only

**One page per handover step**, rather than one screen with four forms on it.
Each is a single job done at a single moment by a single person — a driver at
a vehicle, a dispatcher at a gate — and each carries its own event thread, so
the photo of the scratch is attached to the checkout that found it rather than
to the booking in general.

Detail stays GET-only. It renders the Lifecycle card, but those forms POST to
reservation_lifecycle, so no request to the detail route can ever write.

Layout is ported from the legacy dispatch-asset-record view (HANDOFF.md §9 —
the old interface is the UI specification for *shape*): the four-square action
row, then user/dispatcher checkout side by side, then user/dispatcher return.
The dual-track semantics behind it are the rebuilt ones from
ReservationCheckoutManager, not legacy's.
"""

from __future__ import annotations

from datetime import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.assets.models import Asset, AssetClass, AssetModel, Manufacturer
from app.assets.presentation_layer.search.asset_search import build_meter_rows, search_assets
from app.dispatching.control_layer.factories.reservation_factory import ReservationFactory
from app.dispatching.control_layer.guards.asset_availability_guard import (
    AssetAvailabilityPolicy,
)
from app.dispatching.control_layer.guards.double_booking_guard import DoubleBookingPolicy
from app.dispatching.control_layer.reservation_context import ReservationContext
from app.dispatching.control_layer.managers.reservation_promotion_manager import (
    ReservationPromotionManager,
)
from app.dispatching.models.enums import (
    ConditionRating,
    ReservationStatus,
    ReservationType,
)
from app.events.models.details.dispatching import DispatchingDetail
from app.dispatching.models.reservations.asset_reservation import AssetReservation
from app.dispatching.presentation_layer.search import reservation_search as rs
from app.dispatching.presentation_layer.tools.dispatching_access import (
    accessible_domain_ids,
    can_administer_reservations,
    can_book_reservations,
    can_confirm_reservations,
    can_self_service_for,
    can_self_service_reservations,
    can_verify_handover,
    can_view_reservations,
    is_dispatch_manager,
)
from app.events.presentation_layer.tools.generic_cards import build_activity_card

User = get_user_model()

#: Filter keys the list screen round-trips through the querystring. Named once
#: so the form, the view, and the paging links cannot fall out of step.
LIST_FILTER_KEYS = (
    "q", "asset", "asset_class", "domain", "status",
    "reservation_type", "accountable_person",
)

#: Filter keys the asset picker on the create screen round-trips.
PICKER_FILTER_KEYS = (
    "q", "domain", "asset_class", "model", "manufacturer", "status",
)


# ─────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────

def _parse_datetime_local(raw: str | None):
    """A ``<input type="datetime-local">`` value as an aware datetime."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        naive = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if timezone.is_aware(naive):
        return naive
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _load_reservation(request: HttpRequest, pk: int) -> AssetReservation:
    """The reservation, or 404 — including when the permission gate passed but
    the domain fence did not. §4 of 5_roles_and_permissions.md: a user who may
    not see a record should not learn it exists."""
    reservation = (
        AssetReservation.objects.filter(pk=pk, deleted_at__isnull=True)
        .select_related(
            "asset", "asset__asset_class", "asset__model", "domain",
            "accountable_person", "dispatch",
            "checkout_verified_by", "return_verified_by",
            "user_checked_out_by", "user_checked_in_by",
            "cancelled_by", "conflict_acknowledged_by",
            "initial_meter_read", "final_meter_read",
        )
        .first()
    )
    if reservation is None:
        raise Http404
    if reservation.domain_id not in accessible_domain_ids(request):
        raise Http404
    return reservation


def _form_choices(request: HttpRequest) -> dict:
    domain_ids = accessible_domain_ids(request)
    return {
        "domains": Domain.objects.filter(id__in=domain_ids).order_by("name"),
        "asset_classes": AssetClass.objects.order_by("name"),
        "reservation_types": ReservationType.choices,
        "reservation_statuses": ReservationStatus.choices,
        "condition_ratings": ConditionRating.choices,
        "people": User.objects.filter(is_active=True).order_by("username"),
    }


def _handover_flags(request: HttpRequest, reservation: AssetReservation) -> dict:
    """Which of the four handover actions are live, and why each is not.

    Two independent tracks (3_asset_reservations.md §7.2), so these are four
    separate answers, never one workflow step. Each carries its own `*_reason`
    so a disabled button can say what it is waiting for instead of just
    looking broken — the legacy screen's `title=` tooltips, kept.
    """
    status = reservation.reservation_status
    may_self_service = can_self_service_for(request, reservation)
    may_verify = can_verify_handover(request)

    checkout_verified = reservation.checkout_verified_at is not None
    return_verified = reservation.return_verified_at is not None

    user_out_ok = status == ReservationStatus.CONFIRMED
    user_in_ok = (
        status in (ReservationStatus.CHECKED_OUT, ReservationStatus.USER_CHECKED_OUT)
        and reservation.user_checked_in_by_id is None
    )
    verify_out_ok = (not checkout_verified) and status in (
        ReservationStatus.CONFIRMED,
        ReservationStatus.USER_CHECKED_OUT,
        ReservationStatus.USER_RETURNED,
    )
    verify_in_ok = checkout_verified and (not return_verified) and status in (
        ReservationStatus.CHECKED_OUT,
        ReservationStatus.USER_RETURNED,
    )

    same_as_checkout_actor = (
        reservation.user_checked_out_by_id == request.user.pk
        and status == ReservationStatus.USER_CHECKED_OUT
    )
    same_as_checkin_actor = (
        reservation.user_checked_in_by_id == request.user.pk
        and status == ReservationStatus.USER_RETURNED
    )

    def reason(permitted: bool, state_ok: bool, perm_text: str, state_text: str) -> str:
        if not permitted:
            return perm_text
        if not state_ok:
            return state_text
        return ""

    return {
        "may_self_service": may_self_service,
        "may_verify": may_verify,
        "can_user_checkout": may_self_service and user_out_ok,
        "can_user_checkin": may_self_service and user_in_ok,
        "can_verify_checkout": may_verify and verify_out_ok and not same_as_checkout_actor,
        "can_verify_return": may_verify and verify_in_ok and not same_as_checkin_actor,
        "user_checkout_reason": reason(
            may_self_service, user_out_ok,
            "You are not the accountable person on this booking.",
            "Available once the booking is confirmed.",
        ),
        "user_checkin_reason": reason(
            may_self_service, user_in_ok,
            "You are not the accountable person on this booking.",
            "Available while the asset is checked out.",
        ),
        "verify_checkout_reason": (
            "You filed the user-side checkout — someone else must verify it."
            if may_verify and verify_out_ok and same_as_checkout_actor
            else reason(
                may_verify, verify_out_ok,
                "Requires the Reservation — Verify permission.",
                "Available while the booking is confirmed, user-checked-out, or user-returned.",
            )
        ),
        "verify_return_reason": (
            "You filed the user-side return — someone else must verify it."
            if may_verify and verify_in_ok and same_as_checkin_actor
            else reason(
                may_verify, verify_in_ok,
                "Requires the Reservation — Verify permission.",
                "Available once checkout has been verified by a dispatcher.",
            )
        ),
        "acting_on_behalf": may_self_service
        and reservation.accountable_person_id != request.user.pk,
    }


# ─────────────────────────────────────────────────────────────────────────
# 1. List — calendar, summary rail, filter card
# ─────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def reservation_index(request: HttpRequest) -> HttpResponse:
    if not can_view_reservations(request):
        raise PermissionDenied(
            "Viewing reservations requires the dispatching_read or reservation_book permission."
        )

    filters = {key: request.GET.get(key, "").strip() for key in LIST_FILTER_KEYS}
    requested_for_id = (
        request.GET.get("requested_for")
        or request.GET.get("requested-for")
        or request.GET.get("accountable_person")
        or request.GET.get("accountable-person")
        or ""
    ).strip()
    if requested_for_id:
        filters["accountable_person"] = requested_for_id

    mine_only = request.GET.get("mine") == "1"

    # The window defaults to this month, and the calendar's prev/next arrows
    # move it by re-issuing the same GET with a new range — no separate
    # calendar state, so the grid and the list can never disagree.
    window_start = rs.parse_date(request.GET.get("start"))
    window_end = rs.parse_date(request.GET.get("end"))
    if window_start is None or window_end is None:
        window_start, window_end = rs.default_window()

    reservations = list(
        rs.search_reservations(
            **filters,
            window_start=window_start,
            window_end=window_end,
            mine_only=mine_only,
            actor=request.user,
            domain_ids=accessible_domain_ids(request),
        )
    )

    anchor = window_start
    previous_month = rs.month_bounds(rs.shift_month(anchor, -1))
    next_month = rs.month_bounds(rs.shift_month(anchor, 1))

    # Everything except the window, so the calendar's month arrows carry the
    # active filters with them instead of silently resetting them.
    carried = QueryDict(mutable=True)
    for key, value in filters.items():
        if value:
            carried[key] = value
    if mine_only:
        carried["mine"] = "1"
    querystring_base = carried.urlencode()
    if querystring_base:
        querystring_base += "&"

    return render(request, "dispatching/reservations/index.html", {
        **filters,
        **_form_choices(request),
        "reservations": reservations,
        "summary": rs.summarise(reservations),
        "weeks": rs.build_month_grid(reservations=reservations, anchor=anchor),
        "month_anchor": anchor,
        "window_start": window_start,
        "window_end": window_end,
        "previous_window": previous_month,
        "next_window": next_month,
        "this_window": rs.default_window(),
        "mine_only": mine_only,
        "querystring_base": querystring_base,
        "bookable_assets": Asset.objects.filter(
            domain_id__in=accessible_domain_ids(request), reservations__isnull=False
        ).distinct().order_by("name"),
        "can_book": can_book_reservations(request),
    })


# ─────────────────────────────────────────────────────────────────────────
# 2. Create — asset picker plus the window
# ─────────────────────────────────────────────────────────────────────────

def _picker_context(request: HttpRequest) -> dict:
    """The asset search card: the same multi-field filter set the asset list
    uses (assets/presentation_layer/search/asset_search.py), plus an
    availability window that marks each result free or already claimed."""
    picker = {key: request.GET.get(key, "").strip() for key in PICKER_FILTER_KEYS}
    domain_ids = accessible_domain_ids(request)

    assets = search_assets(**picker).filter(domain_id__in=domain_ids, is_active=True)[:100]

    start = _parse_datetime_local(request.GET.get("scheduled_start"))
    end = _parse_datetime_local(request.GET.get("scheduled_end"))

    rows = []
    for asset in assets:
        available = None
        conflicts: list = []
        if start and end and start < end:
            conflicts = DoubleBookingPolicy.find_overlaps(
                asset_id=asset.pk, scheduled_start=start, scheduled_end=end
            )
            available = not conflicts
        rows.append({"asset": asset, "available": available, "conflicts": conflicts})

    if "only_available_submitted" in request.GET:
        only_available = request.GET.get("only_available") == "1"
    else:
        only_available = True

    if only_available and start and end:
        rows = [row for row in rows if row["available"]]

    return {
        **{f"picker_{k}": v for k, v in picker.items()},
        "asset_rows": rows,
        "models": AssetModel.objects.order_by("model_name"),
        "manufacturers": Manufacturer.objects.order_by("name"),
        "only_available": only_available,
        "window_checked": bool(start and end and start < end),
        "selected_asset_id": request.GET.get("asset_id", "").strip(),
    }


@require_http_methods(["GET"])
def reservation_asset_search(request: HttpRequest) -> HttpResponse:
    """HTMX fragment: the picker's result table on its own, so changing a
    filter re-renders the results without touching the form the user is
    part-way through filling in."""
    if not can_book_reservations(request):
        raise PermissionDenied("Booking an asset requires the reservation_book permission.")
    return render(
        request,
        "dispatching/reservations/_asset_picker_results.html",
        _picker_context(request),
    )


@require_http_methods(["GET", "POST"])
def reservation_create(request: HttpRequest) -> HttpResponse:
    if not can_book_reservations(request):
        raise PermissionDenied("Booking an asset requires the reservation_book permission.")

    dispatch_id = (request.GET.get("dispatch") or request.POST.get("dispatch_id") or "").strip()
    dispatch_obj = None
    if dispatch_id.isdigit():
        dispatch_obj = DispatchingDetail.objects.filter(
            pk=int(dispatch_id), deleted_at__isnull=True, domain_id__in=accessible_domain_ids(request)
        ).first()

    if request.method == "POST":
        asset_id = (request.POST.get("asset_id") or "").strip()
        start = _parse_datetime_local(request.POST.get("scheduled_start"))
        end = _parse_datetime_local(request.POST.get("scheduled_end"))
        accountable_raw = (request.POST.get("accountable_person_id") or "").strip()

        errors: list[str] = []
        if not asset_id.isdigit():
            errors.append("Choose an asset.")
        if start is None or end is None:
            errors.append("A start and an end are both required.")
        elif start >= end:
            errors.append("The start must be before the end.")
        if not accountable_raw.isdigit():
            errors.append("Choose an accountable person.")

        asset = None
        if asset_id.isdigit():
            asset = Asset.objects.filter(
                pk=int(asset_id), domain_id__in=accessible_domain_ids(request)
            ).first()
            if asset is None:
                errors.append("That asset is not in one of your data domains.")

        if not errors:
            try:
                reservation = ReservationFactory.create(
                    asset_id=asset.pk,
                    domain_id=asset.domain_id,
                    reservation_type=request.POST.get("reservation_type") or ReservationType.WORK,
                    accountable_person_id=int(accountable_raw),
                    scheduled_start=start,
                    scheduled_end=end,
                    origin=(request.POST.get("origin") or "").strip(),
                    destination=(request.POST.get("destination") or "").strip(),
                    title=(request.POST.get("title") or "").strip(),
                    description=(request.POST.get("description") or "").strip(),
                    actor=request.user,
                )
                if dispatch_obj:
                    ReservationPromotionManager.promote(
                        reservation_id=reservation.pk,
                        dispatch_id=dispatch_obj.pk,
                        actor=request.user,
                    )
            except (ValueError, User.DoesNotExist) as exc:
                errors.append(str(exc))
            else:
                # Tentative always — only a dispatcher promotes it (§9).
                if not AssetAvailabilityPolicy.is_available(
                    asset_id=asset.pk, scheduled_start=start, scheduled_end=end,
                    exclude_reservation_id=reservation.pk,
                ):
                    messages.warning(
                        request,
                        "This window overlaps another booking on the same asset. The "
                        "claim is tentative, so nothing is blocked — a dispatcher will "
                        "have to acknowledge the conflict to confirm it.",
                    )
                messages.success(request, f"Booking #{reservation.pk} created.")
                if dispatch_obj:
                    messages.success(request, f"Attached booking #{reservation.pk} to Dispatch #{dispatch_obj.pk}.")
                    return redirect(reverse("dispatching_dispatch_edit", kwargs={"pk": dispatch_obj.pk}))
                return redirect(reverse("dispatching_reservation_detail", kwargs={"pk": reservation.pk}))

        for error in errors:
            messages.error(request, error)

    picker = _picker_context(request)
    form_data = {}
    if request.method == "POST":
        picker["selected_asset_id"] = (request.POST.get("asset_id") or "").strip()
        form_data = request.POST
    else:
        scheduled_start = (request.GET.get("scheduled_start") or request.GET.get("start") or "").strip()
        scheduled_end = (request.GET.get("scheduled_end") or request.GET.get("end") or "").strip()
        accountable = (request.GET.get("accountable_person_id") or request.GET.get("accountable_person") or "").strip()
        title = (request.GET.get("title") or "").strip()

        if dispatch_obj:
            if not scheduled_start and dispatch_obj.desired_start:
                scheduled_start = dispatch_obj.desired_start.strftime("%Y-%m-%dT%H:%M")
            if not scheduled_end and dispatch_obj.desired_end:
                scheduled_end = dispatch_obj.desired_end.strftime("%Y-%m-%dT%H:%M")
            if not accountable and dispatch_obj.requested_for_id:
                accountable = str(dispatch_obj.requested_for_id)
            if not title:
                title = f"Reservation for Dispatch #{dispatch_obj.pk}: {dispatch_obj.title}"

        form_data = {
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "accountable_person_id": accountable,
            "title": title,
        }

    return render(request, "dispatching/reservations/create.html", {
        **_form_choices(request),
        **picker,
        "form": form_data,
        "dispatch_obj": dispatch_obj,
    })

# ─────────────────────────────────────────────────────────────────────────
# 3. Detail — the hub. Handover is four links out; lifecycle posts elsewhere
# ─────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def reservation_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """The page people link each other to. It carries the Handover Actions
    card, but those are four *links* — the writes happen on the four handover
    pages, each of which states its own gate and carries its own event thread.

    It also carries a Lifecycle card (confirm / cancel / no-show) for anyone
    holding Reservation — Confirm. Those are real forms.

    # DELIBERATE ANTI-PATTERN: a screen described as "view" holding write
    # controls. Accepted knowingly — a dispatcher clearing a queue should not
    # have to navigate away to confirm a booking they are already looking at.
    # It is contained two ways: the forms POST to reservation_lifecycle, not
    # here, so THIS route stays GET-only and cannot be made to write; and the
    # card renders only for a holder of Reservation — Confirm, so the page a
    # requester sees is unchanged.
    """
    if not can_view_reservations(request):
        raise PermissionDenied(
            "Viewing reservations requires the dispatching_read or reservation_book permission."
        )
    reservation = _load_reservation(request, pk)
    context = ReservationContext(pk, request.user)
    conflicts = DoubleBookingPolicy.find_overlaps(
        asset_id=reservation.asset_id,
        scheduled_start=reservation.scheduled_start,
        scheduled_end=reservation.scheduled_end,
        exclude_reservation_id=reservation.pk,
    )

    own_tentative = (
        reservation.reservation_status == ReservationStatus.TENTATIVE
        and reservation.created_by_id == request.user.pk
    )
    return render(request, "dispatching/reservations/detail.html", {
        **_handover_flags(request, reservation),
        "reservation": reservation,
        "updates": context.struct.updates,
        "meters": build_meter_rows(reservation.asset),
        "activity_card": build_activity_card(reservation, request.user),
        "status_tone": rs.status_tone(reservation.reservation_status),
        "conflicts": conflicts,
        "show_lifecycle": can_confirm_reservations(request),
        "can_confirm": can_confirm_reservations(request)
        and reservation.reservation_status == ReservationStatus.TENTATIVE,
        "can_cancel": (
            can_confirm_reservations(request)
            or (own_tentative and can_book_reservations(request))
        )
        and reservation.reservation_status in rs.OPEN_STATUSES,
        "can_no_show": can_confirm_reservations(request)
        and reservation.reservation_status == ReservationStatus.CONFIRMED,
        "can_edit": can_administer_reservations(request),
    })


# ─────────────────────────────────────────────────────────────────────────
# 4. Lifecycle — confirm, cancel, no-show. POST only, from the detail card
# ─────────────────────────────────────────────────────────────────────────

@require_http_methods(["POST"])
def reservation_lifecycle(request: HttpRequest, pk: int) -> HttpResponse:
    """The write target for the detail page's Lifecycle card.

    Split out so reservation_detail can stay GET-only: the page renders the
    controls, this route accepts them. Permission failures are 403; state
    failures (an illegal transition, an unacknowledged conflict) come back as
    a message on the page, because "not yet" is not "not you".
    """
    reservation = _load_reservation(request, pk)
    action = request.POST.get("action", "")
    context = ReservationContext(pk, request.user)

    try:
        if action == "confirm":
            if not can_confirm_reservations(request):
                raise PermissionDenied("Confirming requires the reservation_confirm permission.")
            context.confirm(
                acknowledge_conflict=request.POST.get("acknowledge_conflict") == "on",
                conflict_reason=(request.POST.get("conflict_reason") or "").strip(),
            )
            messages.success(request, "Booking confirmed.")

        elif action == "cancel":
            # Book covers cancelling your own tentative claim; Confirm covers
            # every other cancellation (§4.2).
            own_tentative = (
                reservation.reservation_status == ReservationStatus.TENTATIVE
                and reservation.created_by_id == request.user.pk
            )
            if not (
                can_confirm_reservations(request)
                or (own_tentative and can_book_reservations(request))
            ):
                raise PermissionDenied(
                    "Cancelling this booking requires the reservation_confirm permission."
                )
            context.cancel(reason=(request.POST.get("reason") or "").strip())
            messages.success(request, "Booking cancelled.")

        elif action == "no_show":
            if not can_confirm_reservations(request):
                raise PermissionDenied(
                    "Recording a no-show requires the reservation_confirm permission."
                )
            context.mark_no_show()
            messages.success(request, "Recorded as a no-show.")

        else:
            raise Http404
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect(reverse("dispatching_reservation_detail", kwargs={"pk": pk}))


# ─────────────────────────────────────────────────────────────────────────
# 5. Handover — four pages, one per track-and-direction
# ─────────────────────────────────────────────────────────────────────────
#
# One template renders all four. They differ in which fields they collect and
# what recording means, not in shape, and a single template keeps the four
# from drifting apart the way legacy's four separate ones had.
#
# The split that matters is not user-vs-dispatcher layout — it is that the
# dispatcher's meters are an official asset reading and the user's are not.

def _float_or_none(raw: str | None) -> float | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _posted_readings(request: HttpRequest) -> dict[int, float]:
    """meter1/meter2 from the form as a {index: value} map, skipping blanks."""
    readings: dict[int, float] = {}
    for index in (1, 2):
        value = _float_or_none(request.POST.get(f"meter{index}"))
        if value is not None:
            readings[index] = value
    return readings


def _render_handover(
    request: HttpRequest,
    reservation: AssetReservation,
    *,
    track: str,
    direction: str,
) -> HttpResponse:
    meters = build_meter_rows(reservation.asset)
    return render(request, "dispatching/reservations/handover.html", {
        **_handover_flags(request, reservation),
        "reservation": reservation,
        "meters": meters,
        # Only meters 1 and 2 are collectable here — those are the columns the
        # user track has. A model defining meters 3-4 still shows them as
        # current readings, they simply are not part of a handover.
        "capturable_meters": [m for m in meters if m.index in (1, 2)],
        "activity_card": build_activity_card(reservation, request.user),
        "status_tone": rs.status_tone(reservation.reservation_status),
        "condition_ratings": ConditionRating.choices,
        "track": track,
        "direction": direction,
        "is_dispatcher_track": track == "dispatcher",
        "is_return": direction == "in",
    })


def _handover_page(
    request: HttpRequest,
    pk: int,
    *,
    track: str,
    direction: str,
    permission_ok,
    permission_error: str,
    run,
    success: str,
) -> HttpResponse:
    reservation = _load_reservation(request, pk)
    if not permission_ok(request, reservation):
        raise PermissionDenied(permission_error)

    if request.method == "POST":
        try:
            run(request, ReservationContext(pk, request.user))
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, success)
            return redirect(reverse("dispatching_reservation_detail", kwargs={"pk": pk}))
        reservation = _load_reservation(request, pk)

    return _render_handover(request, reservation, track=track, direction=direction)


@require_http_methods(["GET", "POST"])
def reservation_user_checkout(request: HttpRequest, pk: int) -> HttpResponse:
    return _handover_page(
        request, pk, track="user", direction="out",
        permission_ok=lambda r, _res: can_self_service_reservations(r),
        permission_error="Self-service checkout requires the reservation_self_service permission.",
        run=lambda r, ctx: ctx.checkout.user_checkout(
            condition=(r.POST.get("condition") or "").strip(),
            notes=(r.POST.get("notes") or "").strip(),
            meter1=_float_or_none(r.POST.get("meter1")),
            meter2=_float_or_none(r.POST.get("meter2")),
            on_behalf=is_dispatch_manager(r),
        ),
        success="User checkout recorded.",
    )


@require_http_methods(["GET", "POST"])
def reservation_user_checkin(request: HttpRequest, pk: int) -> HttpResponse:
    return _handover_page(
        request, pk, track="user", direction="in",
        permission_ok=lambda r, _res: can_self_service_reservations(r),
        permission_error="Self-service return requires the reservation_self_service permission.",
        run=lambda r, ctx: ctx.checkout.user_checkin(
            condition=(r.POST.get("condition") or "").strip(),
            notes=(r.POST.get("notes") or "").strip(),
            meter1=_float_or_none(r.POST.get("meter1")),
            meter2=_float_or_none(r.POST.get("meter2")),
            on_behalf=is_dispatch_manager(r),
        ),
        success="User return recorded.",
    )


@require_http_methods(["GET", "POST"])
def reservation_dispatcher_checkout(request: HttpRequest, pk: int) -> HttpResponse:
    return _handover_page(
        request, pk, track="dispatcher", direction="out",
        permission_ok=lambda r, _res: can_verify_handover(r),
        permission_error="Verifying a handover requires the reservation_verify permission.",
        run=lambda r, ctx: ctx.checkout.dispatcher_verify_checkout(
            checked_out_at=_parse_datetime_local(r.POST.get("checked_out_at")),
            condition=(r.POST.get("condition") or "").strip(),
            notes=(r.POST.get("notes") or "").strip(),
            readings=_posted_readings(r),
        ),
        success="Checkout verified. Meter readings are now the asset's official readings.",
    )


@require_http_methods(["GET", "POST"])
def reservation_dispatcher_checkin(request: HttpRequest, pk: int) -> HttpResponse:
    return _handover_page(
        request, pk, track="dispatcher", direction="in",
        permission_ok=lambda r, _res: can_verify_handover(r),
        permission_error="Verifying a return requires the reservation_verify permission.",
        run=lambda r, ctx: ctx.checkout.dispatcher_verify_return(
            checked_in_at=_parse_datetime_local(r.POST.get("checked_in_at")),
            condition=(r.POST.get("condition") or "").strip(),
            notes=(r.POST.get("notes") or "").strip(),
            readings=_posted_readings(r),
        ),
        success="Return verified. Meter readings are now the asset's official readings.",
    )


# ─────────────────────────────────────────────────────────────────────────
# 6. Edit — every field, dispatch managers only
# ─────────────────────────────────────────────────────────────────────────

#: Fields the edit screen writes directly. Status is NOT among them — it is
#: reached through the lifecycle and handover routes, so the transition guard,
#: the change log, and the narration all still run.
EDITABLE_TEXT_FIELDS = (
    "title", "description", "origin", "destination",
    "dispatcher_checkout_notes", "dispatcher_checkin_notes",
    "user_checkout_notes", "user_checkin_notes",
    "cancellation_reason", "conflict_acknowledgement_reason",
)
EDITABLE_CHOICE_FIELDS = (
    "reservation_type", "condition_out", "condition_in",
    "user_reported_condition_out", "user_reported_condition_in",
)
EDITABLE_DATETIME_FIELDS = (
    "scheduled_start", "scheduled_end", "actual_start", "actual_end",
    "physical_checkout_at", "physical_checkin_at",
    "user_checkout_submitted_at", "user_checkin_submitted_at",
)
#: The user-reported meters. Correctable here because they are reference
#: information — a mistyped digit is just a typo. The *official* readings are
#: MeterHistory rows on the asset and are deliberately not editable from a
#: reservation screen at all.
EDITABLE_FLOAT_FIELDS = (
    "user_meter1_out", "user_meter2_out", "user_meter1_in", "user_meter2_in",
)


@require_http_methods(["GET", "POST"])
def reservation_edit(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_administer_reservations(request):
        raise PermissionDenied(
            "Editing every field on a reservation is restricted to dispatch managers."
        )
    reservation = _load_reservation(request, pk)

    if request.method == "POST":
        for field_name in EDITABLE_TEXT_FIELDS:
            setattr(reservation, field_name, (request.POST.get(field_name) or "").strip())
        for field_name in EDITABLE_CHOICE_FIELDS:
            setattr(reservation, field_name, (request.POST.get(field_name) or "").strip())
        for field_name in EDITABLE_DATETIME_FIELDS:
            setattr(reservation, field_name, _parse_datetime_local(request.POST.get(field_name)))
        for field_name in EDITABLE_FLOAT_FIELDS:
            setattr(reservation, field_name, _float_or_none(request.POST.get(field_name)))

        asset_id = (request.POST.get("asset_id") or "").strip()
        if asset_id.isdigit():
            asset = Asset.objects.filter(
                pk=int(asset_id), domain_id__in=accessible_domain_ids(request)
            ).first()
            if asset is not None:
                reservation.asset_id = asset.pk

        accountable = (request.POST.get("accountable_person_id") or "").strip()
        if accountable.isdigit():
            reservation.accountable_person_id = int(accountable)

        domain_id = (request.POST.get("domain_id") or "").strip()
        if domain_id.isdigit() and int(domain_id) in accessible_domain_ids(request):
            reservation.domain_id = int(domain_id)

        errors: list[str] = []
        if reservation.scheduled_start is None or reservation.scheduled_end is None:
            errors.append("A scheduled start and end are both required.")
        elif reservation.scheduled_start > reservation.scheduled_end:
            errors.append("The scheduled start must not be after the scheduled end.")

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            reservation.updated_by = request.user
            try:
                reservation.save()
            except Exception as exc:  # database constraints are the real rules here
                messages.error(request, f"Refused by a database constraint: {exc}")
            else:
                messages.success(request, "Reservation updated.")
                return redirect(reverse("dispatching_reservation_detail", kwargs={"pk": pk}))

    return render(request, "dispatching/reservations/edit.html", {
        **_form_choices(request),
        "reservation": reservation,
        "assets": Asset.objects.filter(
            domain_id__in=accessible_domain_ids(request)
        ).select_related("asset_class").order_by("name"),
    })
