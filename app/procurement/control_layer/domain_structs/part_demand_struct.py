"""Struct: aggregated read model for one PartDemand.

Derived quantities live here, never as model properties (D53). The legacy
PurchaseOrderLine exposed quantity_received_total, quantity_linked,
total_quantity_linked_from_arrivals, and line_total as @property methods that
each issued their own query, so rendering a 40-line PO cost well over a hundred
queries. Annotate once instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.procurement.control_layer.guards.part_demand_deletion_guard import (
    DeletionVerdict,
    PartDemandDeletionPolicy,
)
from app.procurement.control_layer.narrators.part_demand_narrator import (
    PartDemandNarrator,
)
from app.procurement.models import (
    DIMENSION_FIELDS,
    DemandDimension,
    PartDemand,
    PartDemandUpdate,
    PurchaseOrderDemandLink,
)


@dataclass(frozen=True)
class DemandAllocationSlice:
    """One allocation, flattened for display."""

    link_id: int
    purchase_order_id: int
    po_number: str
    purchase_order_line_id: int
    purchase_order_status: str
    quantity_allocated: Decimal
    is_active: bool


@dataclass(frozen=True)
class PartDemandStruct:
    demand_id: int
    part_id: int
    part_number: str
    part_name: str
    domain_id: int

    demand_state: str
    purchasing_state: str
    shipment_state: str
    issuance_state: str

    quantity_requested: Decimal
    purchased_qty: Decimal
    issued_qty: Decimal

    priority: str
    needed_by: object
    source_module: str
    serial_number_tracking_required: bool
    notes: str
    requested_by_id: int | None

    allocations: tuple[DemandAllocationSlice, ...] = ()

    # Derived — the number the PO wizard caps against (D28).
    outstanding_qty: Decimal = Decimal("0")

    @classmethod
    def load(cls, *, demand_id: int) -> "PartDemandStruct":
        demand = (
            PartDemand.objects.select_related("part")
            .prefetch_related(
                "allocations__purchase_order_line__purchase_order",
            )
            .get(pk=demand_id)
        )
        return cls.from_model(demand)

    @classmethod
    def from_model(cls, demand: PartDemand) -> "PartDemandStruct":
        allocations = tuple(
            DemandAllocationSlice(
                link_id=link.pk,
                purchase_order_id=link.purchase_order_line.purchase_order_id,
                po_number=link.purchase_order_line.purchase_order.po_number,
                purchase_order_line_id=link.purchase_order_line_id,
                purchase_order_status=link.purchase_order_line.purchase_order.status,
                quantity_allocated=link.quantity_allocated,
                is_active=link.is_active,
            )
            for link in demand.allocations.all()
            if link.deleted_at is None
        )
        outstanding = demand.quantity_requested - demand.purchased_qty
        return cls(
            demand_id=demand.pk,
            part_id=demand.part_id,
            part_number=demand.part.part_number,
            part_name=demand.part.name,
            domain_id=demand.domain_id,
            demand_state=demand.demand_state,
            purchasing_state=demand.purchasing_state,
            shipment_state=demand.shipment_state,
            issuance_state=demand.issuance_state,
            quantity_requested=demand.quantity_requested,
            purchased_qty=demand.purchased_qty,
            issued_qty=demand.issued_qty,
            priority=demand.priority,
            needed_by=demand.needed_by,
            source_module=demand.source_module,
            serial_number_tracking_required=demand.serial_number_tracking_required,
            notes=demand.notes,
            requested_by_id=demand.requested_by_id,
            allocations=allocations,
            outstanding_qty=outstanding if outstanding > 0 else Decimal("0"),
        )

    def to_dict(self) -> dict:
        return {
            "demand_id": self.demand_id,
            "part_id": self.part_id,
            "part_number": self.part_number,
            "part_name": self.part_name,
            "domain_id": self.domain_id,
            "demand_state": self.demand_state,
            "purchasing_state": self.purchasing_state,
            "shipment_state": self.shipment_state,
            "issuance_state": self.issuance_state,
            "quantity_requested": self.quantity_requested,
            "purchased_qty": self.purchased_qty,
            "issued_qty": self.issued_qty,
            "outstanding_qty": self.outstanding_qty,
            "priority": self.priority,
            "needed_by": self.needed_by,
            "source_module": self.source_module,
            "serial_number_tracking_required": self.serial_number_tracking_required,
            "notes": self.notes,
            "requested_by_id": self.requested_by_id,
            "allocations": [
                {
                    "link_id": a.link_id,
                    "purchase_order_id": a.purchase_order_id,
                    "po_number": a.po_number,
                    "purchase_order_line_id": a.purchase_order_line_id,
                    "purchase_order_status": a.purchase_order_status,
                    "quantity_allocated": a.quantity_allocated,
                    "is_active": a.is_active,
                }
                for a in self.allocations
            ],
        }


# --------------------------------------------------------------------------- #
# PartDemandDetailStruct family — the detail page's single aggregated read
# (part_demand_workflows.md §2.4). No card on that page issues its own query.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DemandAxisSnapshot:
    """One axis's current value plus when it last moved — the glance-row shape
    (part_demand_workflows.md §2.4's four-axis status card)."""

    dimension: str
    dimension_label: str
    stage: str
    stage_label: str
    last_transition_at: object  # datetime | None — None only for a corrupt row


@dataclass(frozen=True)
class PurchasingCoverageLink:
    """One active PurchaseOrderDemandLink's contribution to this demand's
    purchasing display, per the corrected per-link-then-combine formula
    (po_demand_association_graph.md §2, part_demand_workflows.md Rules section).

    NEVER a per-demand purchased split when is_shared — line_total_requested /
    line_total_allocated / line_total_ordered are the line's totals across every
    active link, not this demand's slice of them (D28's own attribution rule,
    applied to purchasing exactly like shared_demand_sessions.md applies it to
    arrival).
    """

    link_id: int
    purchase_order_id: int
    purchase_order_domain_id: int
    po_number: str
    purchase_order_line_id: int
    line_number: int
    po_status: str
    #: This demand's own requested/allocated figures on this one link — always
    #: safe to show regardless of sharing, since it belongs to this demand.
    quantity_allocated_to_this_demand: Decimal
    #: True when the line's quantity_ordered does not yet cover the sum of
    #: quantity_requested across every demand actively sharing the line — a
    #: display-only label, never written to PurchasingState.
    is_partial: bool
    is_shared: bool
    line_total_requested: Decimal
    line_total_allocated: Decimal
    line_total_ordered: Decimal
    #: (demand_id, quantity_requested) for every OTHER demand sharing this line.
    #: Empty when is_shared is False.
    other_members: tuple[tuple[int, Decimal], ...] = ()


@dataclass(frozen=True)
class DemandJournalRow:
    dimension: str
    dimension_label: str
    from_stage_label: str
    to_stage_label: str
    actor_display: str
    is_system_generated: bool
    notes: str
    flagged_for_review: bool
    created_at: object


@dataclass(frozen=True)
class PartDemandDetailStruct:
    """Extends the PartDemandStruct family (shared_workflows.md §4) rather than
    being a second read path — every field the list/edit views already read via
    PartDemandStruct is available here too, via `.base`."""

    base: PartDemandStruct
    axis_snapshots: tuple[DemandAxisSnapshot, ...]
    purchasing_coverage: tuple[PurchasingCoverageLink, ...]
    journal: tuple[DemandJournalRow, ...]
    deletion_verdict: DeletionVerdict

    @classmethod
    def load(cls, *, demand_id: int) -> "PartDemandDetailStruct":
        base = PartDemandStruct.load(demand_id=demand_id)
        demand = (
            PartDemand.objects.select_related("part", "domain", "requested_by")
            .get(pk=demand_id)
        )

        axis_snapshots = cls._axis_snapshots(demand)
        purchasing_coverage = cls._purchasing_coverage(demand)
        journal = cls._journal(demand)
        deletion_verdict = PartDemandDeletionPolicy.decide(demand=demand)

        return cls(
            base=base,
            axis_snapshots=axis_snapshots,
            purchasing_coverage=purchasing_coverage,
            journal=journal,
            deletion_verdict=deletion_verdict,
        )

    @staticmethod
    def _axis_snapshots(demand: PartDemand) -> tuple[DemandAxisSnapshot, ...]:
        dimension_labels = dict(DemandDimension.choices)
        snapshots = []
        for dimension, field_name in DIMENSION_FIELDS.items():
            stage = getattr(demand, field_name)
            latest = (
                demand.updates.filter(dimension=dimension)
                .order_by("-created_at")
                .first()
            )
            snapshots.append(
                DemandAxisSnapshot(
                    dimension=dimension,
                    dimension_label=dimension_labels.get(dimension, dimension),
                    stage=stage,
                    stage_label=PartDemandNarrator.stage_label(
                        dimension=dimension, stage=stage
                    ),
                    last_transition_at=latest.created_at if latest else None,
                )
            )
        return tuple(snapshots)

    @staticmethod
    def _purchasing_coverage(demand: PartDemand) -> tuple[PurchasingCoverageLink, ...]:
        """The one-hop-plus-one read (po_demand_association_graph.md §2): this
        demand's own active links, and for each linked line, that line's other
        direct links — never those other demands' other lines.

        Deliberately does NOT branch on a graph-membership flag. That branch
        (part_demand_workflows.md §2.4's `is_in_status_graph` case) belongs to
        Phase 4's schema addition, which has not landed as of this wave; every
        demand is treated as the ordinary one-hop case for now.
        """
        active_links = list(
            PurchaseOrderDemandLink.objects.filter(
                part_demand=demand, is_active=True, deleted_at__isnull=True
            ).select_related("purchase_order_line__purchase_order")
        )
        if not active_links:
            return ()

        line_ids = [link.purchase_order_line_id for link in active_links]
        co_links_by_line: dict[int, list[PurchaseOrderDemandLink]] = {}
        for co_link in PurchaseOrderDemandLink.objects.filter(
            purchase_order_line_id__in=line_ids,
            is_active=True,
            deleted_at__isnull=True,
        ).select_related("part_demand"):
            co_links_by_line.setdefault(co_link.purchase_order_line_id, []).append(
                co_link
            )

        results: list[PurchasingCoverageLink] = []
        for link in active_links:
            line = link.purchase_order_line
            siblings = co_links_by_line.get(line.pk, [link])
            line_total_requested = sum(
                (s.part_demand.quantity_requested for s in siblings), Decimal("0")
            )
            line_total_allocated = sum(
                (s.quantity_allocated for s in siblings), Decimal("0")
            )
            is_shared = len(siblings) > 1
            is_partial = line.quantity_ordered < line_total_requested
            other_members = tuple(
                (s.part_demand_id, s.part_demand.quantity_requested)
                for s in siblings
                if s.part_demand_id != demand.pk
            )
            results.append(
                PurchasingCoverageLink(
                    link_id=link.pk,
                    purchase_order_id=line.purchase_order_id,
                    purchase_order_domain_id=line.purchase_order.domain_id,
                    po_number=line.purchase_order.po_number,
                    purchase_order_line_id=line.pk,
                    line_number=line.line_number,
                    po_status=line.purchase_order.status,
                    quantity_allocated_to_this_demand=link.quantity_allocated,
                    is_partial=is_partial,
                    is_shared=is_shared,
                    line_total_requested=line_total_requested,
                    line_total_allocated=line_total_allocated,
                    line_total_ordered=line.quantity_ordered,
                    other_members=other_members,
                )
            )
        return tuple(results)

    @staticmethod
    def _journal(demand: PartDemand) -> tuple[DemandJournalRow, ...]:
        dimension_labels = dict(DemandDimension.choices)
        rows = []
        for update in demand.updates.select_related("actor").order_by("created_at"):
            if update.is_system_generated or update.actor_id is None:
                actor_display = "System"
            else:
                actor_display = str(update.actor)
            rows.append(
                DemandJournalRow(
                    dimension=update.dimension,
                    dimension_label=dimension_labels.get(
                        update.dimension, update.dimension
                    ),
                    from_stage_label=PartDemandNarrator.stage_label(
                        dimension=update.dimension, stage=update.previous_stage
                    )
                    if update.previous_stage or update.dimension == DemandDimension.PURCHASING
                    else "—",
                    to_stage_label=PartDemandNarrator.stage_label(
                        dimension=update.dimension, stage=update.stage
                    ),
                    actor_display=actor_display,
                    is_system_generated=update.is_system_generated,
                    notes=update.notes,
                    flagged_for_review=update.flagged_for_review,
                    created_at=update.created_at,
                )
            )
        return tuple(rows)
