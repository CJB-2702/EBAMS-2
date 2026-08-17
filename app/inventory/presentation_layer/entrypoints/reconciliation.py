"""Reconciliation Hub + per-part reconciliation detail
(`inventory_build_kit/build_plan/05_phase_scan_session_and_reconciliation.md`,
FD-9, FD-26).

Entrypoints stay thin: reads go through `PartReconciliationSearch`/
`ExternalExcessAllocationSearch`, writes go through `IntakeContext.resolve_line`
/ `.pull_external_allocation` — never a raw `PartReconciliationLine.objects...`
write here.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.inventory.control_layer.domain_structs.part_reconciliation_struct import (
    PartReconciliationSessionStruct,
)
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.intake_context import IntakeContext
from app.inventory.models.intake.enums import (
    IntakeSessionStatus,
    ReconciliationResolutionType,
)
from app.inventory.models.intake.part_reconciliation_session import PartReconciliationSession
from app.inventory.presentation_layer.search.intake_search import (
    ExternalExcessAllocationSearch,
    PartReconciliationSearch,
)
from app.inventory.presentation_layer.tools.inventory_access import (
    can_intake,
    require_intake,
)

TEMPLATE_DIR = "inventory/intake"

#: Status filter options shown on the Hub — reconciliation only ever exists
#: while RECONCILING or after the session has since CLOSED with everything
#: resolved; DRAFT/ACTIVE/CANCELLED sessions never carry reconciliation rows.
HUB_STATUS_CHOICES = [
    (IntakeSessionStatus.RECONCILING, "Reconciling"),
    (IntakeSessionStatus.CLOSED, "Closed"),
]


def _int(raw) -> int | None:
    text = str(raw or "").strip()
    return int(text) if text.lstrip("-").isdigit() else None


# --------------------------------------------------------------------------- #
# reconciliation_hub
# --------------------------------------------------------------------------- #


@require_http_methods(["GET"])
def reconciliation_hub(request: HttpRequest) -> HttpResponse:
    status = request.GET.get("status", IntakeSessionStatus.RECONCILING)
    has_unresolved_parts = request.GET.get("has_unresolved_parts", "1") != "0"

    sessions = PartReconciliationSearch.hub_sessions(
        status=status if status != "any" else "",
        has_unresolved_only=has_unresolved_parts,
    )
    rows = [
        {"session": session, **PartReconciliationSearch.summarize(session)}
        for session in sessions
    ]

    context = {
        "rows": rows,
        "filters": {
            "status": status,
            "has_unresolved_parts": has_unresolved_parts,
        },
        "status_choices": HUB_STATUS_CHOICES,
    }
    if request.GET.get("format") == "htmx-search-results":
        return render(
            request, f"{TEMPLATE_DIR}/_reconciliation_hub_results.html", context
        )
    return render(request, f"{TEMPLATE_DIR}/reconciliation_hub.html", context)


# --------------------------------------------------------------------------- #
# reconciliation_detail
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def reconciliation_detail(request: HttpRequest, pk: int) -> HttpResponse:
    reconciliation = get_object_or_404(
        PartReconciliationSession.objects.select_related(
            "part", "intake_session", "intake_session__warehouse"
        ),
        pk=pk,
    )

    if request.method == "POST":
        return _reconciliation_action(request, reconciliation)

    struct = PartReconciliationSessionStruct.from_model(reconciliation)
    lines = list(
        reconciliation.lines.filter(deleted_at__isnull=True)
        .select_related("shipment_line", "shipment_line__shipment")
        .order_by("id")
    )
    # Lines still short their expected quantity — valid pull-in targets for
    # the cross-session excess card (FD-26).
    open_target_lines = [
        {
            "shipment_line_id": line.shipment_line_id,
            "shipment_number": line.shipment_line.shipment.shipment_number,
            "remaining": line.expected_quantity - line.allocated_quantity - line.rejected_quantity,
        }
        for line in lines
        if (line.allocated_quantity + line.rejected_quantity) < line.expected_quantity
    ]
    external_excess = ExternalExcessAllocationSearch.for_part(
        part_id=reconciliation.part_id,
        exclude_session_id=reconciliation.intake_session_id,
    )

    context = {
        "reconciliation": reconciliation,
        "struct": struct,
        "lines": lines,
        "resolution_choices": ReconciliationResolutionType.choices,
        "open_target_lines": open_target_lines,
        "external_excess": external_excess,
        "can_intake": can_intake(request),
    }
    return render(request, f"{TEMPLATE_DIR}/reconciliation_detail.html", context)


def _reconciliation_action(
    request: HttpRequest, reconciliation: PartReconciliationSession
) -> HttpResponse:
    require_intake(request)
    action = request.POST.get("action", "")
    ctx = IntakeContext(reconciliation.intake_session_id)
    back = reverse("inventory_reconciliation_detail", kwargs={"pk": reconciliation.pk})

    try:
        if action == "resolve_line":
            ctx.resolve_line(
                reconciliation_line_id=_int(request.POST.get("reconciliation_line_id")),
                resolution_type=request.POST.get("resolution_type", ""),
                notes=request.POST.get("notes", ""),
                actor=request.user,
            )
            messages.success(request, "Reconciliation line resolved.")
        elif action == "pull_external":
            ctx.pull_external_allocation(
                allocation_id=_int(request.POST.get("allocation_id")),
                target_line_id=_int(request.POST.get("target_line_id")),
                actor=request.user,
            )
            messages.success(request, "External excess allocation pulled in.")
        else:
            messages.error(request, f"Unknown reconciliation action '{action}'.")
    except InventoryValidationError as exc:
        for error in exc.errors:
            messages.error(request, error)

    response = redirect(back)
    response.status_code = 303
    return response
