"""seed_procurement_dev — dev fixture contribution for the Procurement kit.

Everything is built through the REAL control layer (factories, contexts,
managers), never raw ORM inserts, so the seed exercises the same business rules
production would: the four initializing journal rows, D42's auto-approve on
link, D40's status propagation, the D43 completion rollup, and the shared
demand session that forms on a line's second allocation.

The seed deliberately produces one of each interesting shape:

  PO-A  Placed, two lines. Line 1 serves ONE demand      -> attributable
        Line 2 serves TWO demands                        -> shared session
        A shipment arrives against it, partially accepted.
  PO-B  Draft, one line, one allocation with the D42 opt-out — so a demand
        sits unapproved with purchasing_state still unset, which is what Gate 1
        blocking looks like in practice.
  PO-C  Cancelled, demonstrating released allocations and demands returning to
        no purchasing decision.

Plus a demand issued from stock with no PO at all (D11), and one issued then
partly returned (D39), which lands on demand_state=Completed via D43.

Idempotent by po_number/demand marker: safe to re-run.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from app.administration.models import Domain
from app.inventory.control_layer.orchestrators.part_issuance_orchestrator import (
    PartIssuanceOrchestrator,
)
from app.parts.models import Part
from app.procurement.control_layer.adapters.purchase_order_draft_adaptor import (
    DraftAllocation,
    DraftLine,
    PurchaseOrderDraft,
)
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.control_layer.factories.part_demand_factory import (
    PartDemandFactory,
)
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.shipment_context import ShipmentContext
from app.procurement.control_layer.part_demand_context import PartDemandContext
from app.procurement.control_layer.purchase_order_context import PurchaseOrderContext
from app.procurement.models import (
    DemandPriority,
    DemandSourceModule,
    IssuanceState,
    Shipment,
    ShipmentStatus,
    PartDemand,
    PurchaseOrder,
    PurchasingState,
    Vendor,
)

User = get_user_model()

# Domains named the way the authorization model actually reads: a data fence
# for a specific shop at a specific facility.
DOMAIN_SPECS = [
    ("North Acme Ltd — Site A", "north-acme-site-a"),
    ("North Acme Ltd — Site B", "north-acme-site-b"),
]

# Standalone commercial suppliers — unrelated to parts.PartManufacturer.
VENDOR_SPECS = [
    ("Pacific Fastener Supply", "PFS"),
    ("Continental Industrial Distributors", "CID"),
    ("Harborline Trading Co.", "HTC"),
]

SEED_MARKER = "[seeded by seed_procurement_dev]"


class Command(BaseCommand):
    help = "Seed dev Procurement data: demands, purchase orders, shipments, issuance."

    def handle(self, *args, **options):
        actor = (
            User.objects.filter(username="generic_admin").first()
            or User.objects.first()
        )
        if actor is None:
            self.stdout.write(
                self.style.WARNING(
                    "No user found — run the dev_users fixture before "
                    "seed_procurement_dev."
                )
            )
            return

        parts = list(Part.objects.order_by("part_number")[:16])
        if len(parts) < 15:
            self.stdout.write(
                self.style.WARNING(
                    "Fewer than 15 Parts exist — run seed_parts_dev before "
                    "seed_procurement_dev."
                )
            )
            return

        if PurchaseOrder.objects.filter(notes__contains=SEED_MARKER).exists():
            self.stdout.write("Procurement dev seed already present — skipping.")
            return

        vendors = [
            Vendor.objects.get_or_create(name=name, defaults={"code": code})[0]
            for name, code in VENDOR_SPECS
        ]

        domains = [
            Domain.objects.get_or_create(slug=slug, defaults={"name": name})[0]
            for name, slug in DOMAIN_SPECS
        ]
        electronics, mechanical = domains[0], domains[1]

        self._seed_attributable_and_shared(
            actor=actor, vendor=vendors[0], parts=parts, domain=electronics
        )
        self._seed_unapproved_optout(
            actor=actor, vendor=vendors[1], part=parts[2], domain=mechanical
        )
        self._seed_cancelled_order(
            actor=actor, vendor=vendors[2], part=parts[3], domain=mechanical
        )
        self._seed_issued_from_stock(actor=actor, part=parts[0], domain=electronics)
        self._seed_issue_and_return(actor=actor, part=parts[1], domain=electronics)

        # D89 follow-up — graph-node configurations for the GraphSummary
        # visualizer (D79-D88), one method per shape the build session's spec
        # called out as not yet covered by the scenarios above.
        self._seed_graph_simple_triangle(
            actor=actor, vendor=vendors[0], part=parts[4], domain=electronics
        )
        self._seed_graph_demand_split_across_pos(
            actor=actor, vendor_a=vendors[0], vendor_b=vendors[1], part=parts[5], domain=electronics
        )
        self._seed_graph_split_shipment_one_po_line(
            actor=actor, vendor=vendors[1], part=parts[6], domain=mechanical
        )
        self._seed_graph_shipment_line_allocated_across_po_lines(
            actor=actor, vendor=vendors[2], part=parts[7], domain=mechanical
        )
        self._seed_graph_mixed_po_shipment(
            actor=actor,
            vendor_a=vendors[0],
            vendor_b=vendors[2],
            part_a=parts[8],
            part_b=parts[9],
            domain=electronics,
        )
        self._seed_graph_proactive_no_demands(
            actor=actor, vendor=vendors[1], part=parts[10], domain=mechanical
        )
        self._seed_graph_pure_unpurchased_demand(
            actor=actor, part=parts[11], domain=electronics
        )
        self._seed_graph_orphan_shipment_line(
            actor=actor, part=parts[12], domain=mechanical
        )
        self._seed_graph_split_demonstration(
            actor=actor, vendor=vendors[0], part=parts[13], domain=electronics
        )
        self._seed_graph_multi_hop_chain(
            actor=actor, vendor_a=vendors[1], vendor_b=vendors[2], part=parts[14], domain=mechanical
        )

        self.stdout.write(self.style.SUCCESS("Procurement dev seed complete."))

    # ------------------------------------------------------------------ #

    def _demand(
        self,
        *,
        part,
        domain,
        actor,
        quantity,
        priority=DemandPriority.MEDIUM,
        source_module=DemandSourceModule.GENERAL,
        notes="",
    ) -> PartDemand:
        return PartDemandFactory.create(
            part_id=part.pk,
            domain_id=domain.pk,
            quantity_requested=Decimal(quantity),
            priority=priority,
            source_module=source_module,
            notes=f"{notes} {SEED_MARKER}".strip(),
            requested_by=actor,
            actor=actor,
        )

    def _seed_attributable_and_shared(self, *, actor, vendor, parts, domain) -> None:
        """PO-A: one attributable line, one shared demand session, one shipment."""
        sole = self._demand(
            part=parts[0],
            domain=domain,
            actor=actor,
            quantity="10",
            priority=DemandPriority.HIGH,
            notes="Sole demand on its line — arrival is attributable.",
        )
        shared_a = self._demand(
            part=parts[1],
            domain=domain,
            actor=actor,
            quantity="30",
            notes="Shares a line — arrival is a session total only.",
        )
        shared_b = self._demand(
            part=parts[1],
            domain=domain,
            actor=actor,
            quantity="20",
            priority=DemandPriority.CRITICAL,
            notes="Shares a line — arrival is a session total only.",
        )

        draft = PurchaseOrderDraft(
            vendor_id=vendor.pk,
            domain_id=domain.pk,
            vendor_contact="Dana Reyes — turbine desk",
            order_date=timezone.now().date(),
            shipping_cost=Decimal("45.00"),
            tax_amount=Decimal("31.20"),
            notes=f"Routine restock. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=parts[0].pk,
                    quantity_ordered=Decimal("10"),
                    unit_cost=Decimal("12.50"),
                    allocations=[
                        DraftAllocation(
                            demand_id=sole.pk, quantity_allocated=Decimal("10")
                        )
                    ],
                ),
                DraftLine(
                    part_id=parts[1].pk,
                    # 100 ordered against 50 allocated: bulk pricing, with the
                    # remainder legitimately unallocated (D14/D28).
                    quantity_ordered=Decimal("100"),
                    unit_cost=Decimal("3.75"),
                    allocations=[
                        DraftAllocation(
                            demand_id=shared_a.pk, quantity_allocated=Decimal("30")
                        ),
                        DraftAllocation(
                            demand_id=shared_b.pk, quantity_allocated=Decimal("20")
                        ),
                    ],
                ),
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=actor)
        po_context = PurchaseOrderContext(po.pk)
        po_context.submit_for_approval(actor=actor)
        po_context.approve_order(actor=actor)
        po_context.place(actor=actor)

        # A shipment arrives: the sole-demand line in full, the shared line
        # short and partly damaged.
        shipment = ShipmentFactory.create(
            purchase_order=po,
            actor=actor,
            carrier="Overnight Freight",
            shipment_id="1Z-SEED-0001",
            lines=[
                {"part_id": parts[0].pk, "quantity": Decimal("10")},
                {"part_id": parts[1].pk, "quantity": Decimal("60")},
            ],
        )
        context = ShipmentContext(shipment.pk)
        context.advance(to_status=ShipmentStatus.SHIPPED, actor=actor)
        context.advance(to_status=ShipmentStatus.DELIVERED_TO_LOCAL, actor=actor)

        lines = list(shipment.lines.order_by("id"))
        context.accept_line(
            line=lines[0], quantity_accepted=Decimal("10"), actor=actor
        )
        context.accept_line(
            line=lines[1],
            quantity_accepted=Decimal("55"),
            actor=actor,
            rejection_notes="5 units crushed in transit.",
        )

    def _seed_unapproved_optout(self, *, actor, vendor, part, domain) -> None:
        """PO-B: the Buyer opted out of D42's auto-approve, so Gate 1 holds and
        purchasing_state stays unset even after the PO is placed."""
        demand = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="5",
            notes="Buyer preserved the strict approve-first process here.",
        )
        draft = PurchaseOrderDraft(
            vendor_id=vendor.pk,
            domain_id=domain.pk,
            vendor_contact="Sam Okafor — avionics desk",
            order_date=timezone.now().date(),
            notes=f"Awaiting review before placing. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("5"),
                    unit_cost=Decimal("88.00"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand.pk,
                            quantity_allocated=Decimal("5"),
                            auto_approve=False,
                        )
                    ],
                )
            ],
        )
        # Left as Draft deliberately: a real PO not yet sent to the vendor.
        PurchaseOrderFactory.create_from_draft(draft=draft, actor=actor)

    def _seed_cancelled_order(self, *, actor, vendor, part, domain) -> None:
        """PO-C: cancelled after placement. Allocations released, demands back
        to no purchasing decision, free to be bought elsewhere."""
        demand = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="8",
            notes="Vendor could not supply; order cancelled.",
        )
        draft = PurchaseOrderDraft(
            vendor_id=vendor.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Cancelled — vendor discontinued the item. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("8"),
                    unit_cost=Decimal("21.00"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand.pk, quantity_allocated=Decimal("8")
                        )
                    ],
                )
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=actor)
        context = PurchaseOrderContext(po.pk)
        context.submit_for_approval(actor=actor)
        context.approve_order(actor=actor)
        context.place(actor=actor)
        context.cancel(actor=actor, reason="Vendor discontinued the item.")

    def _seed_issued_from_stock(self, *, actor, part, domain) -> None:
        """Issued from stock on hand with no PO ever cut (D11): issuance is
        gated on nothing."""
        demand = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="2",
            notes="Filled from stock on hand; no purchase order.",
        )
        PartIssuanceOrchestrator.issue(
            demand_id=demand.pk,
            issued_to=actor,
            quantity=Decimal("2"),
            to_stage=IssuanceState.ISSUED,
            actor=actor,
            notes="Handed over at the counter.",
        )

    def _seed_issue_and_return(self, *, actor, part, domain) -> None:
        """A borrow-and-return: two signed rows netting down (D39).

        Purchasing is cleared before issuance so the D43 rollup actually fires
        and the demand lands on Completed — the rollup needs purchasing past
        unset/Denied AND issuance at Issued, and whichever is satisfied second
        triggers it. Here that is the return closing issuance out.
        """
        demand = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="4",
            notes="Borrowed 4, returned 1 — issued_qty nets to 3.",
        )
        context = PartDemandContext(demand.pk)
        context.approve(actor=actor, notes="Approved for the shop floor.")
        # Gate 1 is satisfied by the approval above, so purchasing may now move.
        context.set_purchasing_state(
            to_stage=PurchasingState.APPROVED,
            actor=actor,
            notes="Cleared for purchase; filled from stock in the meantime.",
        )

        PartIssuanceOrchestrator.issue(
            demand_id=demand.pk,
            issued_to=actor,
            quantity=Decimal("4"),
            to_stage=IssuanceState.ISSUED_PENDING_RECONCILIATION,
            actor=actor,
            notes="Tooling issued, partial return expected.",
        )
        PartIssuanceOrchestrator.record_return(
            demand_id=demand.pk,
            issued_to=actor,
            quantity=Decimal("1"),
            to_stage=IssuanceState.ISSUED,
            actor=actor,
            notes="One unit returned unused.",
        )

    # ------------------------------------------------------------------ #
    # D89 follow-up — GraphSummary scenario seeds (D79-D88)
    # ------------------------------------------------------------------ #

    def _seed_graph_simple_triangle(self, *, actor, vendor, part, domain) -> None:
        """Scenario 1: the plainest possible graph — one demand, one PO line
        on its own PO, one shipment line, one allocation. No sharing. A contrast
        case against the tangled graphs below when reviewing the visualizer."""
        demand = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="6",
            notes="Graph demo: simple 1:1:1 triangle.",
        )
        draft = PurchaseOrderDraft(
            vendor_id=vendor.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Graph demo: simple triangle. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("6"),
                    unit_cost=Decimal("9.00"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand.pk, quantity_allocated=Decimal("6")
                        )
                    ],
                )
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=actor)
        po_context = PurchaseOrderContext(po.pk)
        po_context.submit_for_approval(actor=actor)
        po_context.approve_order(actor=actor)
        po_context.place(actor=actor)

        shipment = ShipmentFactory.create(
            purchase_order=po,
            actor=actor,
            carrier="Overnight Freight",
            shipment_id="1Z-SEED-0010",
            lines=[{"part_id": part.pk, "quantity": Decimal("6")}],
        )
        context = ShipmentContext(shipment.pk)
        context.advance(to_status=ShipmentStatus.SHIPPED, actor=actor)
        context.advance(to_status=ShipmentStatus.DELIVERED_TO_LOCAL, actor=actor)
        context.accept_line(
            line=shipment.lines.order_by("id").first(),
            quantity_accepted=Decimal("6"),
            actor=actor,
        )

    def _seed_graph_demand_split_across_pos(
        self, *, actor, vendor_a, vendor_b, part, domain
    ) -> None:
        """Scenario 2: one demand allocated across two PO lines on two
        DIFFERENT purchase orders (different vendors), each placed and each
        receiving its own shipment. Should land as ONE graph spanning both
        POs and both shipments, bridged by the single shared demand.

        JUDGMENT CALL: PurchaseOrderDemandLinkValidator._check_cap enforces
        BINARY allocation — a single allocate() call must claim the demand's
        entire outstanding quantity, not an arbitrary partial amount (D28's
        cap is per-demand, exact-match, not a <= ceiling). The first of two
        allocations that together split a demand's need across two orders is
        therefore, by construction, always a partial claim against the FULL
        outstanding amount at that moment, so it must pass
        allow_raise_request=True to bypass the binary check (without also
        setting DraftAllocation.raise_request, which would additionally push
        the demand's quantity_requested down to match — the wrong direction
        for this scenario). The SECOND allocation, once the first has already
        reduced the outstanding amount, exactly matches what remains and
        satisfies the ordinary binary rule with no override needed. Built via
        two explicit PurchaseOrderContext.allocate() calls after each PO is
        placed, rather than through the draft's allocations list, so the
        override can be applied to only the first call."""
        demand = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="40",
            notes="Graph demo: one demand split across two purchase orders.",
        )

        draft_a = PurchaseOrderDraft(
            vendor_id=vendor_a.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Graph demo: demand-split half A. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("25"),
                    unit_cost=Decimal("14.00"),
                    allocations=[],
                )
            ],
        )
        po_a = PurchaseOrderFactory.create_from_draft(draft=draft_a, actor=actor)
        context_a = PurchaseOrderContext(po_a.pk)
        context_a.submit_for_approval(actor=actor)
        context_a.approve_order(actor=actor)
        context_a.place(actor=actor)
        line_a = po_a.lines.order_by("id").first()

        # First half of the split: a genuine partial claim against the
        # demand's full outstanding (40) — needs the override.
        context_a.allocate(
            line=line_a,
            demand=demand,
            quantity_allocated=Decimal("25"),
            actor=actor,
            allow_raise_request=True,
            notes="Buyer split the need across two vendors; first half.",
        )

        draft_b = PurchaseOrderDraft(
            vendor_id=vendor_b.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Graph demo: demand-split half B. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("15"),
                    unit_cost=Decimal("15.50"),
                    allocations=[],
                )
            ],
        )
        po_b = PurchaseOrderFactory.create_from_draft(draft=draft_b, actor=actor)
        context_b = PurchaseOrderContext(po_b.pk)
        context_b.submit_for_approval(actor=actor)
        context_b.approve_order(actor=actor)
        context_b.place(actor=actor)
        line_b = po_b.lines.order_by("id").first()

        # Second half exactly matches what remains outstanding (40 - 25 =
        # 15) — the ordinary binary rule is satisfied with no override.
        context_b.allocate(
            line=line_b,
            demand=demand,
            quantity_allocated=Decimal("15"),
            actor=actor,
            notes="Buyer split the need across two vendors; second half.",
        )

        shipment_a = ShipmentFactory.create(
            purchase_order=po_a,
            actor=actor,
            carrier="Overnight Freight",
            shipment_id="1Z-SEED-0011A",
            lines=[{"part_id": part.pk, "quantity": Decimal("25")}],
        )
        ShipmentContext(shipment_a.pk).advance(
            to_status=ShipmentStatus.SHIPPED, actor=actor
        )

        shipment_b = ShipmentFactory.create(
            purchase_order=po_b,
            actor=actor,
            carrier="Regional Ground",
            shipment_id="1Z-SEED-0011B",
            lines=[{"part_id": part.pk, "quantity": Decimal("15")}],
        )
        ShipmentContext(shipment_b.pk).advance(
            to_status=ShipmentStatus.SHIPPED, actor=actor
        )

        demand.refresh_from_db(fields=["graph_id"])
        line_a.refresh_from_db(fields=["graph_id"])
        line_b.refresh_from_db(fields=["graph_id"])
        assert demand.graph_id == line_a.graph_id == line_b.graph_id, (
            "Graph demo scenario 2 was supposed to bridge one graph across "
            f"two POs; got demand={demand.graph_id} line_a={line_a.graph_id} "
            f"line_b={line_b.graph_id}."
        )

    def _seed_graph_split_shipment_one_po_line(self, *, actor, vendor, part, domain) -> None:
        """Scenario 3: one PO, one line, placed, then TWO separate shipments
        both arrive against it — an early partial shipment and a later
        backorder — both containing a line for the same part, assigned to
        the same PO line."""
        demand = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="20",
            notes="Graph demo: one PO line served by two separate shipments.",
        )
        draft = PurchaseOrderDraft(
            vendor_id=vendor.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Graph demo: split shipment against one line. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("20"),
                    unit_cost=Decimal("6.25"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand.pk, quantity_allocated=Decimal("20")
                        )
                    ],
                )
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=actor)
        context = PurchaseOrderContext(po.pk)
        context.submit_for_approval(actor=actor)
        context.approve_order(actor=actor)
        context.place(actor=actor)
        po_line = po.lines.order_by("id").first()

        # Early partial shipment — the PO has exactly one active line for
        # this part, so ShipmentLineManager.resolve_purchase_order_line
        # auto-assigns it, same as PO-A's shipment above.
        early = ShipmentFactory.create(
            purchase_order=po,
            actor=actor,
            carrier="Overnight Freight",
            shipment_id="1Z-SEED-0012A",
            lines=[{"part_id": part.pk, "quantity": Decimal("12")}],
        )
        ShipmentContext(early.pk).advance(to_status=ShipmentStatus.SHIPPED, actor=actor)

        # Later backorder shipment for the remainder, arriving separately.
        backorder = ShipmentFactory.create(
            purchase_order=po,
            actor=actor,
            carrier="Regional Ground",
            shipment_id="1Z-SEED-0012B",
            lines=[{"part_id": part.pk, "quantity": Decimal("8")}],
        )
        ShipmentContext(backorder.pk).advance(
            to_status=ShipmentStatus.BACKORDERED, actor=actor
        )

        assert (
            early.lines.first()
            .purchase_order_links.get(deleted_at__isnull=True)
            .purchase_order_line_id
            == backorder.lines.first()
            .purchase_order_links.get(deleted_at__isnull=True)
            .purchase_order_line_id
            == po_line.pk
        ), "Both shipments were supposed to auto-resolve onto the same PO line."

    def _seed_graph_shipment_line_allocated_across_po_lines(
        self, *, actor, vendor, part, domain
    ) -> None:
        """Scenario 4: one shipment line arrives claiming a quantity that
        actually belongs to two different PO lines on the same PO (D58's
        "one active line per part" rule is soft, not enforced — two lines for
        the same part is exactly the ambiguous case the allocation tool
        exists for). The arriving line lands unallocated automatically
        (resolve_purchase_order_line refuses to guess between two
        candidates), then ShipmentContext.assign_line allocates each share
        explicitly — TWO ALLOCATION ROWS AGAINST ONE UNCHANGED ARRIVING LINE
        (D90), where the pre-D90 seed produced two sibling shipment lines and
        rewrote the original's quantity."""
        demand_1 = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="9",
            notes="Graph demo: shipment-line split, target line 1.",
        )
        demand_2 = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="6",
            notes="Graph demo: shipment-line split, target line 2.",
        )
        draft = PurchaseOrderDraft(
            vendor_id=vendor.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Graph demo: two lines, same part, deliberately ambiguous. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("9"),
                    unit_cost=Decimal("4.00"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand_1.pk, quantity_allocated=Decimal("9")
                        )
                    ],
                ),
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("6"),
                    unit_cost=Decimal("4.10"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand_2.pk, quantity_allocated=Decimal("6")
                        )
                    ],
                ),
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=actor)
        context = PurchaseOrderContext(po.pk)
        context.submit_for_approval(actor=actor)
        context.approve_order(actor=actor)
        context.place(actor=actor)
        line_1, line_2 = list(po.lines.order_by("id"))

        shipment = ShipmentFactory.create(
            purchase_order=po,
            actor=actor,
            carrier="Overnight Freight",
            shipment_id="1Z-SEED-0013",
            lines=[{"part_id": part.pk, "quantity": Decimal("15")}],
        )
        arriving_line = shipment.lines.order_by("id").first()
        assert not arriving_line.purchase_order_links.filter(
            deleted_at__isnull=True
        ).exists(), (
            "Two active lines for the same part should leave the arriving "
            "shipment line unallocated pending the allocation tool."
        )

        shipment_context = ShipmentContext(shipment.pk)
        shipment_context.assign_line(
            line=arriving_line, quantity=Decimal("9"), purchase_order_line=line_1, actor=actor
        )
        shipment_context.assign_line(
            line=arriving_line, quantity=Decimal("6"), purchase_order_line=line_2, actor=actor
        )
        # The physical row is UNTOUCHED by either call — still one line, still
        # 15, exactly as the packing slip said. That is the whole point of D90:
        # the pre-D90 version of this scenario ended with three shipment-line
        # rows and an original whose quantity had been rewritten to 6.
        arriving_line.refresh_from_db()
        assert arriving_line.quantity == Decimal("15"), (
            "Allocating must never rewrite the arrived quantity."
        )
        assert arriving_line.purchase_order_links.filter(
            deleted_at__isnull=True
        ).count() == 2, "Scenario 4 was supposed to produce two allocations."

    def _seed_graph_mixed_po_shipment(
        self, *, actor, vendor_a, vendor_b, part_a, part_b, domain
    ) -> None:
        """Scenario 5: one shipment, created against a "primary" PO per its
        header, whose lines end up entangled with a DIFFERENT purchase order
        at the packaging level — no shared demand needed, this is purely a
        mixed_po_assignments drift-flag case."""
        demand_a = self._demand(
            part=part_a,
            domain=domain,
            actor=actor,
            quantity="5",
            notes="Graph demo: mixed-PO shipment, primary PO's own part.",
        )
        demand_b = self._demand(
            part=part_b,
            domain=domain,
            actor=actor,
            quantity="3",
            notes="Graph demo: mixed-PO shipment, entangled secondary PO's part.",
        )

        primary_draft = PurchaseOrderDraft(
            vendor_id=vendor_a.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Graph demo: mixed-PO shipment, primary PO. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part_a.pk,
                    quantity_ordered=Decimal("5"),
                    unit_cost=Decimal("7.00"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand_a.pk, quantity_allocated=Decimal("5")
                        )
                    ],
                )
            ],
        )
        primary_po = PurchaseOrderFactory.create_from_draft(draft=primary_draft, actor=actor)
        primary_context = PurchaseOrderContext(primary_po.pk)
        primary_context.submit_for_approval(actor=actor)
        primary_context.approve_order(actor=actor)
        primary_context.place(actor=actor)

        secondary_draft = PurchaseOrderDraft(
            vendor_id=vendor_b.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Graph demo: mixed-PO shipment, secondary PO. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part_b.pk,
                    quantity_ordered=Decimal("3"),
                    unit_cost=Decimal("11.00"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand_b.pk, quantity_allocated=Decimal("3")
                        )
                    ],
                )
            ],
        )
        secondary_po = PurchaseOrderFactory.create_from_draft(draft=secondary_draft, actor=actor)
        secondary_context = PurchaseOrderContext(secondary_po.pk)
        secondary_context.submit_for_approval(actor=actor)
        secondary_context.approve_order(actor=actor)
        secondary_context.place(actor=actor)
        secondary_line = secondary_po.lines.order_by("id").first()

        # Header PO is the primary; part_a's line auto-resolves onto it.
        # part_b matches nothing on the primary PO, so it lands unallocated,
        # then gets allocated explicitly onto the secondary PO's line —
        # the packaging-level entanglement the scenario is demonstrating.
        shipment = ShipmentFactory.create(
            purchase_order=primary_po,
            actor=actor,
            carrier="Overnight Freight",
            shipment_id="1Z-SEED-0014",
            lines=[
                {"part_id": part_a.pk, "quantity": Decimal("5")},
                {"part_id": part_b.pk, "quantity": Decimal("3")},
            ],
        )
        stray_line = shipment.lines.filter(part_id=part_b.pk).first()
        ShipmentContext(shipment.pk).assign_line(
            line=stray_line, purchase_order_line=secondary_line, actor=actor
        )

        shipment.refresh_from_db(fields=["mixed_po_assignments"])
        assert shipment.mixed_po_assignments is True, (
            "Graph demo scenario 5 was supposed to flip mixed_po_assignments "
            "True once a line was allocated onto a different PO's line."
        )

    def _seed_graph_proactive_no_demands(self, *, actor, vendor, part, domain) -> None:
        """Scenario 6 (D14): a PO line — and a shipment against it, at least
        Shipped — with NO PurchaseOrderDemandLink allocated to it at all.
        Bulk/proactive restocking, no demand claims the arrival. Its graph's
        demand_qty should recalculate to 0."""
        draft = PurchaseOrderDraft(
            vendor_id=vendor.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Graph demo: proactive restock, no demands. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("50"),
                    unit_cost=Decimal("2.20"),
                    allocations=[],
                )
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=actor)
        context = PurchaseOrderContext(po.pk)
        context.submit_for_approval(actor=actor)
        context.approve_order(actor=actor)
        context.place(actor=actor)
        po_line = po.lines.order_by("id").first()

        shipment = ShipmentFactory.create(
            purchase_order=po,
            actor=actor,
            carrier="Overnight Freight",
            shipment_id="1Z-SEED-0015",
            lines=[{"part_id": part.pk, "quantity": Decimal("50")}],
        )
        ShipmentContext(shipment.pk).advance(to_status=ShipmentStatus.SHIPPED, actor=actor)

        po_line.refresh_from_db(fields=["graph_id"])
        summary = po_line.graph
        assert summary.demand_qty == 0, (
            "Graph demo scenario 6's graph was supposed to have demand_qty "
            f"== 0 with no demand links; got {summary.demand_qty}."
        )

    def _seed_graph_pure_unpurchased_demand(self, *, actor, part, domain) -> None:
        """Scenario 7: a PartDemand created and left with no PO link at all.
        Sits alone in a single-member graph (node-init, no merge ever
        happens)."""
        demand = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="3",
            notes="Graph demo: pure unpurchased demand, no PO ever attached.",
        )
        assert demand.graph_id is not None

    def _seed_graph_orphan_shipment_line(self, *, actor, part, domain) -> None:
        """Scenario 8: a shipment line created with no allocation at all
        (arrived matching nothing, no header PO either).

        ShipmentLineManager.add_line unconditionally calls
        GraphSummaryManager.initialize_node for every new line — including an
        unassigned one — and only conditionally merges afterward if a PO line
        was resolved. So an orphan shipment line does NOT sit outside the
        graph system; it gets its own fresh single-member GraphSummary, same
        as a pure unpurchased demand does. This seed documents that actual
        behavior rather than the "no graph_id at all" outcome one might
        assume from D82's prose."""
        shipment = ShipmentFactory.create(
            domain=domain,
            actor=actor,
            carrier="Unmarked Van",
            shipment_id="1Z-SEED-0016",
            notes=f"Graph demo: orphan shipment line, no PO on file. {SEED_MARKER}",
            lines=[{"part_id": part.pk, "quantity": Decimal("1")}],
        )
        line = shipment.lines.order_by("id").first()
        assert not line.purchase_order_links.filter(deleted_at__isnull=True).exists()
        assert line.graph_id is not None, (
            "ShipmentLineManager.add_line initializes a node even for an "
            "unallocated line — the orphan line still gets its own "
            "single-member graph, not a null graph_id."
        )

    def _seed_graph_split_demonstration(self, *, actor, vendor, part, domain) -> None:
        """Scenario 9: build a small graph (one demand, one PO line, placed,
        shipment delivered and accepted), then delink the one allocation via
        PurchaseOrderContext.delink (the caller-facing verb over
        PurchaseOrderDemandLinkManager.delink). The PO line + shipment line
        keep their existing graph; the now-unlinked demand splits off onto a
        freshly created GraphSummary — the one scenario in this file where a
        graph genuinely divides into two live summaries."""
        demand = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="7",
            notes="Graph demo: built then delinked to demonstrate a real graph split.",
        )
        draft = PurchaseOrderDraft(
            vendor_id=vendor.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Graph demo: split demonstration. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("7"),
                    unit_cost=Decimal("3.30"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand.pk, quantity_allocated=Decimal("7")
                        )
                    ],
                )
            ],
        )
        po = PurchaseOrderFactory.create_from_draft(draft=draft, actor=actor)
        po_context = PurchaseOrderContext(po.pk)
        po_context.submit_for_approval(actor=actor)
        po_context.approve_order(actor=actor)
        po_context.place(actor=actor)
        po_line = po.lines.order_by("id").first()

        shipment = ShipmentFactory.create(
            purchase_order=po,
            actor=actor,
            carrier="Overnight Freight",
            shipment_id="1Z-SEED-0017",
            lines=[{"part_id": part.pk, "quantity": Decimal("7")}],
        )
        shipment_context = ShipmentContext(shipment.pk)
        shipment_context.advance(to_status=ShipmentStatus.SHIPPED, actor=actor)
        shipment_context.advance(to_status=ShipmentStatus.DELIVERED_TO_LOCAL, actor=actor)
        shipment_line = shipment.lines.order_by("id").first()
        shipment_context.accept_line(
            line=shipment_line, quantity_accepted=Decimal("7"), actor=actor
        )

        graph_id_before = po_line.graph_id
        demand.refresh_from_db(fields=["graph_id"])
        assert demand.graph_id == graph_id_before

        from app.procurement.models import PurchaseOrderDemandLink

        link = PurchaseOrderDemandLink.objects.get(
            part_demand=demand, purchase_order_line=po_line, deleted_at__isnull=True
        )
        po_context = PurchaseOrderContext(po.pk)
        po_context.delink(link=link, actor=actor)

        demand.refresh_from_db(fields=["graph_id"])
        po_line.refresh_from_db(fields=["graph_id"])
        assert demand.graph_id != po_line.graph_id, (
            "Graph demo scenario 9 was supposed to split into two graphs on "
            f"delink; both landed on graph {demand.graph_id}."
        )

    def _seed_graph_multi_hop_chain(self, *, actor, vendor_a, vendor_b, part, domain) -> None:
        """Scenario 10: demand A allocated to PO-line-1; demand B ALSO
        allocated to PO-line-1 (shared session with A); demand B separately
        allocated to PO-line-2 on a DIFFERENT purchase order; PO-line-2
        shared with demand C. End state: A, B, C, PO-line-1, and PO-line-2
        (plus their POs) should all land on ONE graph despite spanning two
        POs and three demands with no direct A-C link — bridged entirely
        through demand B's dual allocation.

        Same binary-allocation judgment call as scenario 2: demand B's first
        share (6 of its 12 outstanding) is a genuine partial claim and needs
        PurchaseOrderContext.allocate(..., allow_raise_request=True); its
        second share (the remaining 6) exactly matches what is left
        outstanding and needs no override. Demand A and demand C are each
        allocated their full amount in one shot, same as PO-A's attributable
        line, so they go through the draft's allocations list normally."""
        demand_a = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="10",
            notes="Graph demo: multi-hop chain, demand A on PO-line-1.",
        )
        demand_b = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="12",
            notes="Graph demo: multi-hop chain, demand B bridges PO-line-1 and PO-line-2.",
        )
        demand_c = self._demand(
            part=part,
            domain=domain,
            actor=actor,
            quantity="8",
            notes="Graph demo: multi-hop chain, demand C on PO-line-2.",
        )

        draft_1 = PurchaseOrderDraft(
            vendor_id=vendor_a.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Graph demo: multi-hop chain, PO 1. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("22"),
                    unit_cost=Decimal("5.00"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand_a.pk, quantity_allocated=Decimal("10")
                        ),
                    ],
                )
            ],
        )
        po_1 = PurchaseOrderFactory.create_from_draft(draft=draft_1, actor=actor)
        context_1 = PurchaseOrderContext(po_1.pk)
        context_1.submit_for_approval(actor=actor)
        context_1.approve_order(actor=actor)
        context_1.place(actor=actor)
        line_1 = po_1.lines.order_by("id").first()

        # Demand B's first share: a genuine partial claim (6 of 12
        # outstanding) — needs the override, same reasoning as scenario 2.
        context_1.allocate(
            line=line_1,
            demand=demand_b,
            quantity_allocated=Decimal("6"),
            actor=actor,
            allow_raise_request=True,
            notes="Demand B's first share, bridging PO-line-1.",
        )

        draft_2 = PurchaseOrderDraft(
            vendor_id=vendor_b.pk,
            domain_id=domain.pk,
            order_date=timezone.now().date(),
            notes=f"Graph demo: multi-hop chain, PO 2. {SEED_MARKER}",
            lines=[
                DraftLine(
                    part_id=part.pk,
                    quantity_ordered=Decimal("14"),
                    unit_cost=Decimal("5.50"),
                    allocations=[
                        DraftAllocation(
                            demand_id=demand_c.pk, quantity_allocated=Decimal("8")
                        ),
                    ],
                )
            ],
        )
        po_2 = PurchaseOrderFactory.create_from_draft(draft=draft_2, actor=actor)
        context_2 = PurchaseOrderContext(po_2.pk)
        context_2.submit_for_approval(actor=actor)
        context_2.approve_order(actor=actor)
        context_2.place(actor=actor)
        line_2 = po_2.lines.order_by("id").first()

        # Demand B's remaining outstanding need (12 - 6 = 6) allocated here —
        # exactly matches what is left, so the ordinary binary rule is
        # satisfied with no override. This is the bridge to PO-line-2's
        # graph.
        context_2.allocate(
            line=line_2,
            demand=demand_b,
            quantity_allocated=Decimal("6"),
            actor=actor,
            notes="Demand B's second share, bridging PO-line-2.",
        )

        demand_a.refresh_from_db(fields=["graph_id"])
        demand_b.refresh_from_db(fields=["graph_id"])
        demand_c.refresh_from_db(fields=["graph_id"])
        line_1.refresh_from_db(fields=["graph_id"])
        line_2.refresh_from_db(fields=["graph_id"])
        graph_ids = {
            demand_a.graph_id,
            demand_b.graph_id,
            demand_c.graph_id,
            line_1.graph_id,
            line_2.graph_id,
        }
        assert len(graph_ids) == 1, (
            "Graph demo scenario 10 was supposed to land A, B, C, and both "
            f"PO lines on one graph; got {graph_ids}."
        )
