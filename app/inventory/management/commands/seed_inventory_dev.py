"""seed_inventory_dev — dev fixture contribution for the Inventory build.

Everything is built through the real control layer (`TopographyContext`,
`StockLedgerManager`), never raw ORM inserts, per the same discipline
`seed_procurement_dev` follows.

Phase 1 (topography): two warehouses under different divisions/domain sets,
each with its factory-provisioned Intake Room plus 2-3 named storage rooms
(one carrying an excluded domain), and storage locations spanning numeric
(zero-padded) and non-numeric coordinates.

Phase 2 (stock): unassigned Intake-Room stock, located stock at several
storage locations, serialized unit rows for an `sn_expected` part, and one
part deliberately present in two rooms — seeded exclusively through
`StockLedgerManager.inject` so that write seam is exercised daily.

Phase 3 (SVG spatial engine, FD-29): a dedicated "Spatial Map Demo" room in
Warehouse A, seeded with RoomLocations/StorageLocations matching the
relabeled Inkscape fixtures under `app/inventory/tests/fixtures/`, with the
real Room-tier and RoomLocation-tier SVGs uploaded through
`TopographyContext.upload_room_layout`/`upload_room_location_layout` — a
working two-image spatial map end to end, not a raw ORM attachment.

Phase 4 (intake engine, FD-13): three reactive (PO-less) shipments seeded via
the real `ShipmentFactory`, received through the real `IntakeContext`/
`AutoIntakeManager` write path — never a raw `ItemAllocation.objects.create`:
one fully received (closed pseudo-session -> Intake Room stock), one
partially received (line split, remaining balance left open), and one
manual-allocation session carrying an extra unlinked allocation
(`shipment_line=NULL` — excess held in the intake room, a terminal state).

Idempotent: skipped entirely when the marker warehouse code already exists.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand

from app.administration.models import Division, Domain
from app.assets.models import Asset
from app.inventory.control_layer.adapters.coordinate_adaptor import format_xyz_coordinate
from app.inventory.control_layer.intake_context import IntakeContext
from app.inventory.control_layer.managers.stock_ledger_manager import StockLedgerManager
from app.inventory.control_layer.movement_context import MovementContext
from app.inventory.control_layer.orchestrators.part_issuance_orchestrator import (
    PartIssuanceOrchestrator,
)
from app.inventory.control_layer.topography_context import TopographyContext
from app.inventory.models.intake.enums import (
    AllocationCondition,
    IntakeSessionMethod,
)
from app.inventory.models.issuance.enums import IssueType
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.room_location import RoomLocation
from app.inventory.models.topography.storage_location import StorageLocation
from app.inventory.models.topography.warehouse import Warehouse
from app.parts.models import Part
from app.procurement.control_layer.factories.part_demand_factory import (
    PartDemandFactory,
)
from app.procurement.control_layer.factories.shipment_factory import ShipmentFactory
from app.procurement.models import IssuanceState

User = get_user_model()

WAREHOUSE_A_CODE = "WH-NORTH-01"
WAREHOUSE_B_CODE = "WH-SOUTH-01"

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
DEV_DIR = Path(__file__).resolve().parents[4] / "_dev"
ROOM_LAYOUT_FIXTURE = FIXTURES_DIR / "room_layout_los_angeles.svg"
ROOM_LOCATION_LAYOUT_FIXTURE = FIXTURES_DIR / "room_location_layout_bins.svg"
GRID_6X4_ROOM_LAYOUT_FIXTURE = DEV_DIR / "6x4_grid_room_layout.svg"
AISLE_SHELF_ROOM_LAYOUT_FIXTURE = DEV_DIR / "aisle_shelf_room_layout.svg"
BINS_5X5_LOCATION_LAYOUT_FIXTURE = DEV_DIR / "5x5_grid_bins_layout.svg"

# The Room-tier fixture's 7 shape codes (RoomLocation.display_code, XY only).
# "0005-0002" is the one wired up with its own Z-picker (bins) SVG; the rest
# are single-StorageLocation XYs with no second-tier image, exercising the
# "skip tier 3" UX shortcut.
ROOM_LAYOUT_SHAPE_CODES = [
    "0005-0002", "0002-0001", "0001-0001",
    "0005-0001", "0004-0001", "0003-0001", "0001-0002",
]
Z_PICKER_ROOM_LOCATION_CODE = "0005-0002"
# The RoomLocation-tier fixture's 9 shape codes (StorageLocation.atomic_coord).
BIN_LAYOUT_ATOMIC_CODES = [
    "0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009",
]


class Command(BaseCommand):
    help = "Seed dev Inventory data: warehouses, rooms, storage locations, stock."

    def handle(self, *args, **options):
        actor = (
            User.objects.filter(username="generic_admin").first()
            or User.objects.first()
        )
        if actor is None:
            self.stdout.write(
                self.style.WARNING(
                    "No user found — run the dev_users fixture before "
                    "seed_inventory_dev."
                )
            )
            return

        if Warehouse.objects.filter(code=WAREHOUSE_A_CODE).exists():
            self.stdout.write("Inventory dev seed already present — skipping.")
            return

        north = Division.objects.filter(slug="north").first()
        south = Division.objects.filter(slug="south").first()
        if north is None or south is None:
            self.stdout.write(
                self.style.WARNING(
                    "North/South divisions not found — run the administration "
                    "dev fixtures before seed_inventory_dev."
                )
            )
            return

        north_domains = list(
            Domain.objects.filter(slug__in=["north-acme-site-a", "north-beta-site-a"])
        )
        south_domains = list(
            Domain.objects.filter(slug__in=["south-acme-site-a", "south-beta-site-a"])
        )

        warehouse_a = self._seed_warehouse(
            actor=actor,
            name="North Distribution Center",
            code=WAREHOUSE_A_CODE,
            division=north,
            domains=north_domains,
            numeric_prefix=True,
        )
        warehouse_b = self._seed_warehouse(
            actor=actor,
            name="South Distribution Center",
            code=WAREHOUSE_B_CODE,
            division=south,
            domains=south_domains,
            numeric_prefix=False,
        )

        self._seed_stock(actor=actor, warehouse=warehouse_a, warehouse_b=warehouse_b)
        self._seed_svg_demo_room(actor=actor, warehouse=warehouse_a)
        self._seed_6x4_grid_room(actor=actor, warehouse=warehouse_a)
        self._seed_aisle_shelf_room(actor=actor, warehouse=warehouse_a)
        self._seed_intake_scenarios(
            actor=actor, warehouse=warehouse_a, domain=north_domains[0]
        )
        self._seed_scan_scenarios(
            actor=actor, warehouse=warehouse_a, domain=north_domains[0]
        )
        self._seed_movements_and_issuance(
            actor=actor,
            warehouse=warehouse_a,
            warehouse_b=warehouse_b,
            domain=north_domains[0],
        )
        self._seed_audit_scenarios(actor=actor, warehouse=warehouse_a)

        self.stdout.write(self.style.SUCCESS("Inventory dev seed complete."))

    def _seed_warehouse(
        self, *, actor, name: str, code: str, division, domains, numeric_prefix: bool
    ) -> Warehouse:
        context = TopographyContext.create_warehouse(
            name=name,
            code=code,
            division_id=division.pk,
            address=f"{name} — dev fixture",
            domain_ids=[d.pk for d in domains],
            actor=actor,
        )

        racking = context.add_room(
            room_name="Racking",
            description="General shelving racks.",
            actor=actor,
        )
        overflow = context.add_room(
            room_name="Overflow",
            description="Overflow storage — excluded from the second domain.",
            excluded_domain_ids=[domains[1].pk] if len(domains) > 1 else None,
            actor=actor,
        )

        if numeric_prefix:
            # North Distribution Center: seed rooms with RoomLocation & StorageLocation shapes
            # matching old application SVG fixtures (LosAngelesMainStoreroom + bin_layout_example),
            # and upload the corresponding layout SVGs to Racking and Overflow.
            for room in (racking, overflow):
                room_locations: dict[str, RoomLocation] = {}
                for code in ROOM_LAYOUT_SHAPE_CODES:
                    major, minor = code.split("-")
                    room_locations[code] = context.add_room_location(
                        room_id=room.pk, major_coord=major, minor_coord=minor, actor=actor
                    )

                z_picker_loc = room_locations[Z_PICKER_ROOM_LOCATION_CODE]
                context.bulk_add_storage_locations(
                    room_location_id=z_picker_loc.pk,
                    atomic_coords=BIN_LAYOUT_ATOMIC_CODES,
                    actor=actor,
                )
                for code, rl in room_locations.items():
                    if code == Z_PICKER_ROOM_LOCATION_CODE:
                        continue
                    context.add_storage_location(
                        room_location_id=rl.pk, atomic_coord="0001", actor=actor
                    )

                if ROOM_LAYOUT_FIXTURE.exists():
                    with ROOM_LAYOUT_FIXTURE.open("rb") as fh:
                        room_upload = SimpleUploadedFile(
                            ROOM_LAYOUT_FIXTURE.name, fh.read(), content_type="image/svg+xml"
                        )
                    context.upload_room_layout(
                        room_id=room.pk, uploaded_file=room_upload, actor=actor
                    )

                if ROOM_LOCATION_LAYOUT_FIXTURE.exists():
                    with ROOM_LOCATION_LAYOUT_FIXTURE.open("rb") as fh:
                        bins_upload = SimpleUploadedFile(
                            ROOM_LOCATION_LAYOUT_FIXTURE.name, fh.read(), content_type="image/svg+xml"
                        )
                    context.upload_room_location_layout(
                        room_location_id=z_picker_loc.pk, uploaded_file=bins_upload, actor=actor
                    )
        else:
            coordinates = [
                (f"AISLE-A{major}", f"SHELF-{minor}", str(atomic))
                for major in (1, 2)
                for minor in (1, 2, 3)
                for atomic in (1, 2)
            ]
            half = len(coordinates) // 2
            self._seed_coordinates(
                context=context, room_id=racking.pk, coordinates=coordinates[:half], actor=actor
            )
            self._seed_coordinates(
                context=context, room_id=overflow.pk, coordinates=coordinates[half:], actor=actor
            )

        return context.warehouse

    def _seed_coordinates(self, *, context, room_id, coordinates, actor) -> None:
        """Groups (major, minor, atomic) triples into RoomLocations (Tier 2)
        each carrying their atomic StorageLocations (Tier 3), per FD-29. Keys
        by the adaptor's own zero-padded formatting so lookups match what the
        factory actually stores."""
        by_xy: dict[tuple[str, str], list[str]] = {}
        for major, minor, atomic in coordinates:
            key = (format_xyz_coordinate(major), format_xyz_coordinate(minor))
            by_xy.setdefault(key, []).append(atomic)

        room_locations = context.bulk_add_room_locations(
            room_id=room_id, coordinates=list(by_xy.keys()), actor=actor
        )
        for room_location in room_locations:
            atomics = by_xy[(room_location.major_coord, room_location.minor_coord)]
            context.bulk_add_storage_locations(
                room_location_id=room_location.pk, atomic_coords=atomics, actor=actor
            )

    def _seed_stock(self, *, actor, warehouse, warehouse_b) -> None:
        parts = list(Part.objects.order_by("part_number")[:5])
        if len(parts) < 3:
            self.stdout.write(
                self.style.WARNING(
                    "Fewer than 3 Parts exist — run seed_parts_dev before "
                    "seed_inventory_dev's stock section."
                )
            )
            return

        intake_room = warehouse.rooms.get(is_intake_room=True)
        racking_room = warehouse.rooms.get(room_name="Racking")
        racking_locations = StorageLocation.objects.filter(
            room_location__room=racking_room
        ).order_by("id")
        first_location = racking_locations[0]
        second_location = racking_locations[1]

        # Unassigned stock straight in the Intake Room.
        StockLedgerManager.inject(
            warehouse=warehouse,
            room=intake_room,
            storage_location=None,
            part=parts[0],
            qty=Decimal("50"),
            unit_cost=Decimal("4.250"),
            actor=actor,
        )

        # Located stock at a real storage location.
        StockLedgerManager.inject(
            warehouse=warehouse,
            room=racking_room,
            storage_location=first_location,
            part=parts[1],
            qty=Decimal("12"),
            unit_cost=Decimal("9.500"),
            actor=actor,
        )

        # Serialized unit rows for an sn_expected part.
        sn_part = parts[2]
        if not sn_part.sn_expected:
            sn_part.sn_expected = True
            sn_part.updated_by = actor
            sn_part.save(update_fields=["sn_expected", "updated_by", "updated_at"])
        for serial in ("SN-0001", "SN-0002", "SN-0003"):
            StockLedgerManager.inject(
                warehouse=warehouse,
                room=racking_room,
                storage_location=second_location,
                part=sn_part,
                qty=Decimal("1"),
                serial=serial,
                unit_cost=Decimal("120.000"),
                actor=actor,
            )

        # One part present in two rooms (racking here, intake in warehouse B).
        shared_part = parts[3] if len(parts) > 3 else parts[0]
        StockLedgerManager.inject(
            warehouse=warehouse,
            room=racking_room,
            storage_location=first_location,
            part=shared_part,
            qty=Decimal("8"),
            actor=actor,
        )
        b_intake_room = warehouse_b.rooms.get(is_intake_room=True)
        StockLedgerManager.inject(
            warehouse=warehouse_b,
            room=b_intake_room,
            storage_location=None,
            part=shared_part,
            qty=Decimal("6"),
            actor=actor,
        )

    def _seed_svg_demo_room(self, *, actor, warehouse) -> None:
        """A dedicated room wired up with real Room-tier and RoomLocation-
        tier SVGs, uploaded through the real control-layer path (never raw
        ORM `FileField` assignment) — Phase 3's SVG spatial engine demo."""
        if not ROOM_LAYOUT_FIXTURE.exists() or not ROOM_LOCATION_LAYOUT_FIXTURE.exists():
            self.stdout.write(
                self.style.WARNING(
                    "SVG spatial-engine fixtures missing — skipping the demo room."
                )
            )
            return

        context = TopographyContext(warehouse.pk)
        demo_room = context.add_room(
            room_name="Spatial Map Demo",
            description="Interactive SVG spatial map — seeded end to end for Phase 3.",
            actor=actor,
        )

        room_locations: dict[str, RoomLocation] = {}
        for code in ROOM_LAYOUT_SHAPE_CODES:
            major, minor = code.split("-")
            room_locations[code] = context.add_room_location(
                room_id=demo_room.pk, major_coord=major, minor_coord=minor, actor=actor
            )

        z_picker_room_location = room_locations[Z_PICKER_ROOM_LOCATION_CODE]
        context.bulk_add_storage_locations(
            room_location_id=z_picker_room_location.pk,
            atomic_coords=BIN_LAYOUT_ATOMIC_CODES,
            actor=actor,
        )
        for code, room_location in room_locations.items():
            if code == Z_PICKER_ROOM_LOCATION_CODE:
                continue
            context.add_storage_location(
                room_location_id=room_location.pk, atomic_coord="0001", actor=actor
            )

        with ROOM_LAYOUT_FIXTURE.open("rb") as fh:
            room_upload = SimpleUploadedFile(
                ROOM_LAYOUT_FIXTURE.name, fh.read(), content_type="image/svg+xml"
            )
        context.upload_room_layout(
            room_id=demo_room.pk, uploaded_file=room_upload, actor=actor
        )

        with ROOM_LOCATION_LAYOUT_FIXTURE.open("rb") as fh:
            bins_upload = SimpleUploadedFile(
                ROOM_LOCATION_LAYOUT_FIXTURE.name, fh.read(), content_type="image/svg+xml"
            )
        context.upload_room_location_layout(
            room_location_id=z_picker_room_location.pk, uploaded_file=bins_upload, actor=actor
        )

    def _seed_6x4_grid_room(self, *, actor, warehouse) -> None:
        """Seeds a dedicated 6x4 Grid Storage Room with 24 room locations
        (0001-0001 through 0004-0006) and uploads the 6x4_grid_room_layout.svg layout."""
        if not GRID_6X4_ROOM_LAYOUT_FIXTURE.exists():
            self.stdout.write(
                self.style.WARNING(
                    "6x4 grid SVG layout fixture missing — skipping 6x4 grid room."
                )
            )
            return

        context = TopographyContext(warehouse.pk)
        grid_room = context.add_room(
            room_name="6x4 Grid Room",
            description="6x4 Matrix Storage Room with 24 interactive locations.",
            actor=actor,
        )

        grid_coords = [
            (f"{major:04d}", f"{minor:04d}")
            for major in range(1, 5)
            for minor in range(1, 7)
        ]

        room_locations = context.bulk_add_room_locations(
            room_id=grid_room.pk, coordinates=grid_coords, actor=actor
        )

        for rl in room_locations:
            context.add_storage_location(
                room_location_id=rl.pk, atomic_coord="0001", actor=actor
            )

        with GRID_6X4_ROOM_LAYOUT_FIXTURE.open("rb") as fh:
            grid_upload = SimpleUploadedFile(
                GRID_6X4_ROOM_LAYOUT_FIXTURE.name, fh.read(), content_type="image/svg+xml"
            )
        context.upload_room_layout(
            room_id=grid_room.pk, uploaded_file=grid_upload, actor=actor
        )

    def _seed_aisle_shelf_room(self, *, actor, warehouse) -> None:
        """Seeds an Aisle & Rack Storage Room with 4 aisles x 5 racks (20 room locations)
        and uploads aisle_shelf_room_layout.svg as room layout, plus 5x5_grid_bins_layout.svg
        on room location 0001-0001."""
        if not AISLE_SHELF_ROOM_LAYOUT_FIXTURE.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Aisle shelf SVG layout fixture missing — skipping aisle shelf room."
                )
            )
            return

        context = TopographyContext(warehouse.pk)
        aisle_room = context.add_room(
            room_name="Aisle & Rack Storage Room",
            description="4-Aisle Distribution Center Floorplan with 20 Pallet Rack Bays.",
            actor=actor,
        )

        aisle_coords = [
            (f"{major:04d}", f"{minor:04d}")
            for major in range(1, 5)
            for minor in range(1, 6)
        ]

        room_locations = context.bulk_add_room_locations(
            room_id=aisle_room.pk, coordinates=aisle_coords, actor=actor
        )

        # Wire up 0001-0001 with 5x5 bin Z-picker layout
        z_picker_loc = None
        for rl in room_locations:
            if rl.display_code == "0001-0001":
                z_picker_loc = rl
                atomic_bins = [f"{b:04d}" for b in range(1, 26)]
                context.bulk_add_storage_locations(
                    room_location_id=rl.pk, atomic_coords=atomic_bins, actor=actor
                )
            else:
                context.add_storage_location(
                    room_location_id=rl.pk, atomic_coord="0001", actor=actor
                )

        with AISLE_SHELF_ROOM_LAYOUT_FIXTURE.open("rb") as fh:
            room_upload = SimpleUploadedFile(
                AISLE_SHELF_ROOM_LAYOUT_FIXTURE.name, fh.read(), content_type="image/svg+xml"
            )
        context.upload_room_layout(
            room_id=aisle_room.pk, uploaded_file=room_upload, actor=actor
        )

        if z_picker_loc and BINS_5X5_LOCATION_LAYOUT_FIXTURE.exists():
            with BINS_5X5_LOCATION_LAYOUT_FIXTURE.open("rb") as fh:
                bins_upload = SimpleUploadedFile(
                    BINS_5X5_LOCATION_LAYOUT_FIXTURE.name, fh.read(), content_type="image/svg+xml"
                )
            context.upload_room_location_layout(
                room_location_id=z_picker_loc.pk, uploaded_file=bins_upload, actor=actor
            )

    def _seed_intake_scenarios(self, *, actor, warehouse, domain) -> None:
        """Three Phase 4 receiving scenarios, all through the real
        `IntakeContext`/`AutoIntakeManager` write path against reactive
        (PO-less) shipments built via `ShipmentFactory`."""
        parts = list(Part.objects.order_by("part_number")[:3])
        if len(parts) < 3:
            self.stdout.write(
                self.style.WARNING(
                    "Fewer than 3 Parts exist — skipping Phase 4 intake seed scenarios."
                )
            )
            return

        # Scenario 1: fully received -> closed pseudo-session -> Intake Room stock.
        full_shipment = ShipmentFactory.create(
            domain=domain,
            lines=[{"part_id": parts[0].pk, "quantity": Decimal("10")}],
            actor=actor,
            shipment_id="DEV-FULL-0001",
            notes="Phase 4 dev seed — full receipt.",
        )
        full_line = full_shipment.lines.get(deleted_at__isnull=True)
        IntakeContext.commit_auto_intake(
            operator=actor,
            warehouse_id=warehouse.pk,
            room_id=None,
            shipment_id=full_shipment.pk,
            line_targets={full_line.pk: (Decimal("10"), Decimal("0"))},
            actor=actor,
        )

        # Scenario 2: partially received -> line split, remainder left open.
        partial_shipment = ShipmentFactory.create(
            domain=domain,
            lines=[{"part_id": parts[1].pk, "quantity": Decimal("20")}],
            actor=actor,
            shipment_id="DEV-PARTIAL-0001",
            notes="Phase 4 dev seed — partial receipt.",
        )
        partial_line = partial_shipment.lines.get(deleted_at__isnull=True)
        IntakeContext.commit_auto_intake(
            operator=actor,
            warehouse_id=warehouse.pk,
            room_id=None,
            shipment_id=partial_shipment.pk,
            line_targets={partial_line.pk: (Decimal("12"), Decimal("0"))},
            actor=actor,
        )

        # Scenario 3: manual session with an extra unmanifested allocation.
        unmanifested_shipment = ShipmentFactory.create(
            domain=domain,
            lines=[{"part_id": parts[2].pk, "quantity": Decimal("5")}],
            actor=actor,
            shipment_id="DEV-UNMANIFESTED-0001",
            notes="Phase 4 dev seed — unmanifested overage.",
        )
        unmanifested_line = unmanifested_shipment.lines.get(deleted_at__isnull=True)
        manual_context = IntakeContext.start_session(
            operator=actor,
            warehouse_id=warehouse.pk,
            room_id=None,
            intake_method=IntakeSessionMethod.MANUAL_PACKAGE,
            actor=actor,
        )
        manual_context.associate_shipment(shipment_id=unmanifested_shipment.pk, actor=actor)
        manual_context.create_manual_allocation(
            shipment_line_id=unmanifested_line.pk,
            part_id=parts[2].pk,
            quantity=Decimal("5"),
            condition=AllocationCondition.GOOD,
            actor=actor,
        )
        manual_context.create_manual_allocation(
            shipment_line_id=None,
            part_id=parts[0].pk,
            quantity=Decimal("2"),
            condition=AllocationCondition.GOOD,
            actor=actor,
        )
        manual_context.close_session(actor=actor)

    def _seed_scan_scenarios(self, *, actor, warehouse, domain) -> None:
        """Phase 5 dev seed — two scan sessions, both through the real
        `IntakeContext` write path, so the intake surfaces are demonstrable
        after every `refresh_project.py` reset (this whole method only ever
        runs once — guarded by the top-level
        `Warehouse.objects.filter(code=WAREHOUSE_A_CODE).exists()`
        short-circuit at the top of `handle`, same as every other `_seed_*`
        method in this file).

        Scenario 1 — a mid-flight ACTIVE scan session: one shipment with two
        lines expecting the SAME part (N-to-M), and an unlinked
        (`shipment_line=NULL`) GOOD allocation for that part too small to
        satisfy either line's expected quantity alone, so
        `IntakeMatchingManager.execute_fifo_cascade` has nothing to do yet —
        exactly the "staged, ambiguous, cascade hasn't fired" state the scan
        portal's unlinked card should show.

        Scenario 2 — a short receipt plus unlinked excess. Three lines are
        under-received and a fourth part arrives with no manifest line at
        all. Nothing is reconciled, approved, or closed, because there is no
        such act any more (intake_portal_workflow.md §7.1): a discrepancy is
        derived live from the numbers, and unlinked excess is a terminal
        state, not a pending task (§7.2).

        The excess part is deliberately the SAME part left unlinked in
        Scenario 1, so Phase 2's allocation portal (§7.3) — whose whole point
        is that excess counted in one session can fill a shortage found in
        another — has real cross-session stock to find.
        """
        parts = list(Part.objects.order_by("part_number")[:3])
        if len(parts) < 3:
            self.stdout.write(
                self.style.WARNING(
                    "Fewer than 3 Parts exist — skipping Phase 5 scan seed scenarios."
                )
            )
            return
        part_x, part_y, part_z = parts[0], parts[1], parts[2]

        # ---- Scenario 1: ACTIVE scan session, N-to-M unlinked, no cascade yet.
        ntom_shipment = ShipmentFactory.create(
            domain=domain,
            lines=[
                {"part_id": part_x.pk, "quantity": Decimal("10")},
                {"part_id": part_x.pk, "quantity": Decimal("10")},
            ],
            actor=actor,
            shipment_id="DEV-SCAN-NTOM-0001",
            notes="Phase 5 dev seed — N-to-M ambiguous scan staging.",
        )
        scan_session = IntakeContext.start_session(
            operator=actor,
            warehouse_id=warehouse.pk,
            room_id=None,
            intake_method=IntakeSessionMethod.SCAN,
            actor=actor,
        )
        scan_session.associate_shipment(shipment_id=ntom_shipment.pk, actor=actor)
        # Ambiguous — two open lines expect part_x, so a real scan would leave
        # this unlinked rather than pick one. Created directly via the
        # manual-allocation verb (same effect as an ambiguous `process_scan`,
        # without needing a real barcode payload for the seed): 3 < either
        # line's 10 expected, so the FIFO cascade has nothing to fill yet.
        scan_session.create_manual_allocation(
            shipment_line_id=None,
            part_id=part_x.pk,
            quantity=Decimal("3"),
            condition=AllocationCondition.GOOD,
            actor=actor,
        )
        # Leave ACTIVE — do not close.

        # ---- Scenario 2: short receipt + unlinked excess, left ACTIVE.
        short_shipment = ShipmentFactory.create(
            domain=domain,
            lines=[
                {"part_id": part_x.pk, "quantity": Decimal("10")},  # short line A
                {"part_id": part_x.pk, "quantity": Decimal("10")},  # short line B
                {"part_id": part_y.pk, "quantity": Decimal("5")},   # short line C
            ],
            actor=actor,
            shipment_id="DEV-SHORT-0001",
            notes="Phase 5 dev seed — short receipt + unlinked excess demo.",
        )
        short_lines = list(
            short_shipment.lines.filter(deleted_at__isnull=True).order_by("id")
        )
        line_a, line_b, line_c = short_lines[0], short_lines[1], short_lines[2]

        short_session = IntakeContext.start_session(
            operator=actor,
            warehouse_id=warehouse.pk,
            room_id=None,
            intake_method=IntakeSessionMethod.SCAN,
            actor=actor,
        )
        short_session.associate_shipment(shipment_id=short_shipment.pk, actor=actor)
        # Each line under-received. The shortage is DERIVED from these numbers
        # on every read (§11.2) — no row records it, so nothing can drift.
        short_session.create_manual_allocation(
            shipment_line_id=line_a.pk, part_id=part_x.pk,
            quantity=Decimal("6"), condition=AllocationCondition.GOOD, actor=actor,
        )
        short_session.create_manual_allocation(
            shipment_line_id=line_b.pk, part_id=part_x.pk,
            quantity=Decimal("7"), condition=AllocationCondition.GOOD, actor=actor,
        )
        short_session.create_manual_allocation(
            shipment_line_id=line_c.pk, part_id=part_y.pk,
            quantity=Decimal("4"), condition=AllocationCondition.GOOD, actor=actor,
        )
        # Genuinely unmanifested stock (part_z) — no matching line anywhere, so
        # it stays unlinked. That is its terminal state, not a pending task.
        short_session.create_manual_allocation(
            shipment_line_id=None, part_id=part_z.pk,
            quantity=Decimal("2"), condition=AllocationCondition.GOOD, actor=actor,
        )
        # Left ACTIVE and unposted — nothing to sign off, nothing to resolve.

    def _seed_movements_and_issuance(
        self, *, actor, warehouse, warehouse_b, domain
    ) -> None:
        """Phase 6: putaway two Intake Room rows, one inter-warehouse
        transfer, and issues covering all three `IssueType`s (one serialized,
        one returned) — all through `MovementContext`/
        `PartIssuanceOrchestrator`, never a raw `PartMovement`/`PartIssue`
        insert."""
        parts = list(Part.objects.order_by("part_number")[:5])
        if len(parts) < 4:
            self.stdout.write(
                self.style.WARNING(
                    "Fewer than 4 Parts exist — skipping Phase 6 movement/issuance seed."
                )
            )
            return

        intake_room = warehouse.rooms.get(is_intake_room=True)
        racking_room = warehouse.rooms.get(room_name="Racking")
        racking_locations = list(
            StorageLocation.objects.filter(room_location__room=racking_room).order_by("id")
        )
        putaway_target_a, putaway_target_b = racking_locations[2], racking_locations[3]

        # Putaway two unassigned Intake Room rows into real storage locations.
        unassigned_rows = list(
            ActiveInventory.objects.filter(room=intake_room, is_unassigned=True).order_by("id")[:2]
        )
        putaway_targets = [putaway_target_a, putaway_target_b]
        for row, target in zip(unassigned_rows, putaway_targets):
            MovementContext.putaway(
                active_inventory_id=row.pk,
                to_storage_location_id=target.pk,
                actor=actor,
            )

        # Inter-warehouse transfer: 3 units of the shared part, landing
        # unassigned in Warehouse B's Intake Room automatically.
        shared_part = parts[3]
        shared_row = ActiveInventory.objects.filter(
            warehouse=warehouse, part=shared_part, serial_number=""
        ).first()
        if shared_row is not None:
            MovementContext.move(
                active_inventory_id=shared_row.pk,
                to_warehouse_id=warehouse_b.pk,
                quantity=Decimal("3"),
                actor=actor,
                notes="Phase 6 dev seed — inter-warehouse transfer.",
            )

        # Demand-linked issue (non-serialized), followed by a partial return.
        located_row = ActiveInventory.objects.filter(
            warehouse=warehouse, storage_location=putaway_target_a
        ).first() or ActiveInventory.objects.filter(
            warehouse=warehouse, room=racking_room, serial_number=""
        ).first()
        if located_row is not None and located_row.quantity_on_hand >= 2:
            demand = PartDemandFactory.create(
                part_id=located_row.part_id,
                domain_id=domain.pk,
                quantity_requested=Decimal("2"),
                requested_by=actor,
                notes="Phase 6 dev seed — filled from putaway stock.",
                actor=actor,
            )
            PartIssuanceOrchestrator.issue(
                quantity=Decimal("2"),
                issue_type=IssueType.FOR_PART_DEMAND,
                demand_id=demand.pk,
                issued_to=actor,
                active_inventory_id=located_row.pk,
                to_stage=IssuanceState.ISSUED_PENDING_RECONCILIATION,
                actor=actor,
                notes="Phase 6 dev seed — demand-linked issue.",
            )
            PartIssuanceOrchestrator.record_return(
                quantity=Decimal("1"),
                issue_type=IssueType.FOR_PART_DEMAND,
                demand_id=demand.pk,
                issued_to=actor,
                active_inventory_id=located_row.pk,
                to_stage=IssuanceState.ISSUED,
                actor=actor,
                notes="Phase 6 dev seed — partial return.",
            )

        # Direct-to-asset issue.
        asset = Asset.objects.filter(is_active=True).first()
        direct_asset_row = ActiveInventory.objects.filter(
            warehouse=warehouse, room=racking_room, serial_number=""
        ).exclude(pk=getattr(located_row, "pk", None)).first()
        if asset is not None and direct_asset_row is not None and direct_asset_row.quantity_on_hand >= 1:
            PartIssuanceOrchestrator.issue(
                quantity=Decimal("1"),
                issue_type=IssueType.DIRECT_TO_ASSET,
                issued_to_asset_id=asset.pk,
                active_inventory_id=direct_asset_row.pk,
                actor=actor,
                notes="Phase 6 dev seed — direct-to-asset issue.",
            )

        # Direct-to-user, serialized issue.
        serial_row = ActiveInventory.objects.filter(
            warehouse=warehouse, room=racking_room
        ).exclude(serial_number="").first()
        if serial_row is not None:
            PartIssuanceOrchestrator.issue(
                quantity=Decimal("1"),
                issue_type=IssueType.DIRECT_TO_USER,
                issued_to=actor,
                active_inventory_id=serial_row.pk,
                actor=actor,
                notes="Phase 6 dev seed — direct-to-user serialized issue.",
            )

    def _seed_audit_scenarios(self, *, actor, warehouse) -> None:
        """Phase 7: create one finalized Spot Check with direct adjustments,
        and one open Full Room audit with an unrecorded transfer."""
        from app.inventory.control_layer.audit_session_context import AuditSessionContext
        from app.inventory.models.audit.enums import AuditResolutionType
        from app.inventory.models.audit.audit_session import AuditSessionType
        
        parts = list(Part.objects.order_by("part_number")[:5])
        if len(parts) < 2:
            return

        racking_room = warehouse.rooms.get(room_name="Racking")
        
        # Scenario 1: Completed Spot Check
        ctx1 = AuditSessionContext.start(
            warehouse_id=warehouse.pk,
            room_id=racking_room.pk,
            conducted_by=actor,
            session_type=AuditSessionType.SPOT_CHECK,
            notes="Phase 7 dev seed — completed spot check with a direct adjustment.",
            actor=actor,
        )
        # Find a row to adjust
        row1 = ActiveInventory.objects.filter(room=racking_room).first()
        if row1:
            line = ctx1.record_line(
                part_id=row1.part_id,
                storage_location_id=row1.storage_location_id,
                serial_number=row1.serial_number,
                counted_qty=row1.quantity_on_hand + Decimal("1"),
                actor=actor,
            )
            ctx1.set_resolution(line_id=line.pk, resolution_type=AuditResolutionType.DIRECT_ADJUSTMENT, actor=actor)
            ctx1.finalize(actor=actor)
            
        # Scenario 2: Open Full Room Audit
        ctx2 = AuditSessionContext.start(
            warehouse_id=warehouse.pk,
            room_id=racking_room.pk,
            conducted_by=actor,
            session_type=AuditSessionType.FULL_ROOM_AUDIT,
            notes="Phase 7 dev seed — open full room audit with an unrecorded transfer pending.",
            actor=actor,
        )
        # Find a different row
        row2 = ActiveInventory.objects.filter(room=racking_room).exclude(pk=row1.pk if row1 else 0).first()
        if row2:
            # Matched line
            ctx2.record_line(
                part_id=row2.part_id,
                storage_location_id=row2.storage_location_id,
                serial_number=row2.serial_number,
                counted_qty=row2.quantity_on_hand,
                actor=actor,
            )
        # An unrecorded transfer line (surplus of a part not there)
        row3 = ActiveInventory.objects.filter(room=warehouse.rooms.get(is_intake_room=True)).first()
        if row3:
            line_transfer = ctx2.record_line(
                part_id=row3.part_id,
                storage_location_id=row2.storage_location_id if row2 else None,
                counted_qty=Decimal("2"),
                actor=actor,
            )
            ctx2.set_resolution(line_id=line_transfer.pk, resolution_type=AuditResolutionType.UNRECORDED_TRANSFER, actor=actor)
