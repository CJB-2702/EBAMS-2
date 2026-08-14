"""seed_procurement_dev — dev fixture contribution for the Procurement kit.

Everything is built through the REAL control layer (factories, contexts,
managers), never raw ORM inserts, so the seed exercises the same business rules
production would: the four initializing journal rows, D42's auto-approve on
link, D40's status propagation, the D43 completion rollup, and the shared
demand session that forms on a line's second allocation.

The seed deliberately produces one of each interesting shape:

  PO-A  Placed, two lines. Line 1 serves ONE demand      -> attributable
        Line 2 serves TWO demands                        -> shared session
        A package arrives against it, partially accepted.
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
from app.procurement.control_layer.factories.package_factory import PackageFactory
from app.procurement.control_layer.factories.part_demand_factory import (
    PartDemandFactory,
)
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.package_context import PackageContext
from app.procurement.control_layer.part_demand_context import PartDemandContext
from app.procurement.control_layer.purchase_order_context import PurchaseOrderContext
from app.procurement.models import (
    DemandPriority,
    DemandSourceModule,
    IssuanceState,
    Package,
    PackageStatus,
    PartDemand,
    PurchaseOrder,
    PurchasingState,
    Vendor,
)

User = get_user_model()

# Domains named the way the authorization model actually reads: a data fence
# for a specific shop at a specific facility.
DOMAIN_SPECS = [
    ("San Diego — Electronics Shop", "sd-ele"),
    ("San Diego — Mechanical Shop", "sd-mech"),
]

# Standalone commercial suppliers — unrelated to parts.PartManufacturer.
VENDOR_SPECS = [
    ("Pacific Fastener Supply", "PFS"),
    ("Continental Industrial Distributors", "CID"),
    ("Harborline Trading Co.", "HTC"),
]

SEED_MARKER = "[seeded by seed_procurement_dev]"


class Command(BaseCommand):
    help = "Seed dev Procurement data: demands, purchase orders, packages, issuance."

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

        parts = list(Part.objects.order_by("part_number")[:6])
        if len(parts) < 4:
            self.stdout.write(
                self.style.WARNING(
                    "Fewer than 4 Parts exist — run seed_parts_dev before "
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
        """PO-A: one attributable line, one shared demand session, one package."""
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

        # A package arrives: the sole-demand line in full, the shared line
        # short and partly damaged.
        package = PackageFactory.create(
            purchase_order=po,
            actor=actor,
            carrier="Overnight Freight",
            shipment_id="1Z-SEED-0001",
            lines=[
                {"part_id": parts[0].pk, "quantity": Decimal("10")},
                {"part_id": parts[1].pk, "quantity": Decimal("60")},
            ],
        )
        context = PackageContext(package.pk)
        context.advance(to_status=PackageStatus.SHIPPED, actor=actor)
        context.advance(to_status=PackageStatus.DELIVERED_TO_LOCAL, actor=actor)

        lines = list(package.lines.order_by("id"))
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
