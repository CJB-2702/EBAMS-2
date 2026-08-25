"""Storeroom-designer port acceptance tests: the stock-protection rules.

Three claims, each stated once here and enforced in exactly one place in the
control layer:

1. A bin (`StorageLocation`) holding stock cannot be retired.
2. An XY location whose bins hold stock cannot be retired either — the parent
   is not a way around the child check.
3. A replacement layout SVG that has no shape for a stock-holding location is
   rejected outright: nothing archived, `current_layout` untouched.

Plus the warehouse CRUD surface: created with its Intake Room, retired
softly, never hard-deleted.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from app.administration.models import Division
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.managers.stock_ledger_manager import StockLedgerManager
from app.inventory.control_layer.topography_context import TopographyContext
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.warehouse import Warehouse
from app.parts.control_layer.factories.part_factory import PartFactory

User = get_user_model()

#: Layer group is `locations`; shapes are labeled with the XY display code.
ROOM_SVG_BOTH = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="200" height="200">
  <g inkscape:label="locations">
    <rect inkscape:label="0001-0001" x="0" y="0" width="10" height="10" />
    <rect inkscape:label="0002-0002" x="20" y="0" width="10" height="10" />
  </g>
</svg>"""

#: Same map with `0001-0001` removed — that is the stocked location.
ROOM_SVG_DROPS_STOCKED = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="200" height="200">
  <g inkscape:label="locations">
    <rect inkscape:label="0002-0002" x="20" y="0" width="10" height="10" />
  </g>
</svg>"""

#: Same map with the *empty* location removed instead.
ROOM_SVG_DROPS_EMPTY = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="200" height="200">
  <g inkscape:label="locations">
    <rect inkscape:label="0001-0001" x="0" y="0" width="10" height="10" />
  </g>
</svg>"""

BINS_SVG_DROPS_STOCKED = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="100" height="100">
  <g inkscape:label="bins">
    <rect inkscape:label="0002" x="10" y="0" width="10" height="10" />
  </g>
</svg>"""


class TopographyStockGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="topo_guard", email="topo_guard@test.local",
            password="TestPass123!@",
        )
        cls.division = Division.objects.create(
            name="Guard Division", slug="guard-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="Guard Warehouse", code="WH-GUARD",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.part = PartFactory.create(
            data={"part_number": "PN-GUARD-01", "name": "Guarded Widget"},
            actor=cls.user,
        )

    def setUp(self):
        self.context = TopographyContext(self.warehouse.pk)
        self.room = self.context.add_room(room_name="Main Storeroom", actor=self.user)
        # 0001-0001 will hold stock; 0002-0002 stays empty.
        self.stocked_xy = self.context.add_room_location(
            room_id=self.room.pk, major_coord="1", minor_coord="1", actor=self.user
        )
        self.empty_xy = self.context.add_room_location(
            room_id=self.room.pk, major_coord="2", minor_coord="2", actor=self.user
        )
        self.stocked_bin = self.context.add_storage_location(
            room_location_id=self.stocked_xy.pk, atomic_coord="1", actor=self.user
        )
        self.empty_bin = self.context.add_storage_location(
            room_location_id=self.stocked_xy.pk, atomic_coord="2", actor=self.user
        )
        StockLedgerManager.inject(
            warehouse=self.warehouse,
            room=self.room,
            storage_location=self.stocked_bin,
            part=self.part,
            qty=Decimal("4"),
            actor=self.user,
        )

    # ------------------------------------------------------------------ #
    # 1. Bins
    # ------------------------------------------------------------------ #

    def test_retiring_a_bin_holding_stock_is_refused(self):
        with self.assertRaises(InventoryValidationError) as ctx:
            self.context.deactivate_storage_location(
                storage_location=self.stocked_bin, actor=self.user
            )
        self.assertIn(self.stocked_bin.display_code, str(ctx.exception))
        self.stocked_bin.refresh_from_db()
        self.assertTrue(self.stocked_bin.is_active)

    def test_retiring_an_empty_bin_succeeds(self):
        self.context.deactivate_storage_location(
            storage_location=self.empty_bin, actor=self.user
        )
        self.empty_bin.refresh_from_db()
        self.assertFalse(self.empty_bin.is_active)

    def test_bin_becomes_retirable_once_its_stock_is_withdrawn(self):
        StockLedgerManager.withdraw(
            room=self.room, storage_location=self.stocked_bin,
            part=self.part, qty=Decimal("4"), actor=self.user,
        )
        self.context.deactivate_storage_location(
            storage_location=self.stocked_bin, actor=self.user
        )
        self.stocked_bin.refresh_from_db()
        self.assertFalse(self.stocked_bin.is_active)

    # ------------------------------------------------------------------ #
    # 2. XY locations
    # ------------------------------------------------------------------ #

    def test_retiring_an_xy_location_with_stock_underneath_is_refused(self):
        with self.assertRaises(InventoryValidationError):
            self.context.deactivate_room_location(
                room_location=self.stocked_xy, actor=self.user
            )
        self.stocked_xy.refresh_from_db()
        self.assertTrue(self.stocked_xy.is_active)

    def test_retiring_an_empty_xy_location_succeeds(self):
        self.context.deactivate_room_location(
            room_location=self.empty_xy, actor=self.user
        )
        self.empty_xy.refresh_from_db()
        self.assertFalse(self.empty_xy.is_active)

    # ------------------------------------------------------------------ #
    # 3. Layout uploads
    # ------------------------------------------------------------------ #

    def _upload_room(self, payload: bytes):
        return self.context.upload_room_layout(
            room_id=self.room.pk,
            uploaded_file=SimpleUploadedFile(
                "room.svg", payload, content_type="image/svg+xml"
            ),
            actor=self.user,
        )

    def test_layout_that_drops_a_stocked_location_is_rejected(self):
        self._upload_room(ROOM_SVG_BOTH)
        self.room.refresh_from_db()
        first_layout_id = self.room.current_layout_id

        with self.assertRaises(InventoryValidationError) as ctx:
            self._upload_room(ROOM_SVG_DROPS_STOCKED)
        self.assertIn("0001-0001", str(ctx.exception))

        # Nothing archived: the room still points at the first layout.
        self.room.refresh_from_db()
        self.assertEqual(self.room.current_layout_id, first_layout_id)

    def test_layout_that_drops_only_an_empty_location_is_accepted(self):
        result = self._upload_room(ROOM_SVG_DROPS_EMPTY)
        self.assertEqual(result.orphaned, ("0002-0002",))
        self.room.refresh_from_db()
        self.assertIsNotNone(self.room.current_layout_id)

    def test_override_flag_lets_a_stock_orphaning_layout_through(self):
        result = self.context.upload_room_layout(
            room_id=self.room.pk,
            uploaded_file=SimpleUploadedFile(
                "room.svg", ROOM_SVG_DROPS_STOCKED, content_type="image/svg+xml"
            ),
            actor=self.user,
            allow_orphaned_stock=True,
        )
        self.assertIn("0001-0001", result.orphaned)

    def test_bin_layout_that_drops_a_stocked_bin_is_rejected(self):
        with self.assertRaises(InventoryValidationError) as ctx:
            self.context.upload_room_location_layout(
                room_location_id=self.stocked_xy.pk,
                uploaded_file=SimpleUploadedFile(
                    "bins.svg", BINS_SVG_DROPS_STOCKED, content_type="image/svg+xml"
                ),
                actor=self.user,
            )
        self.assertIn("0001", str(ctx.exception))
        self.stocked_xy.refresh_from_db()
        self.assertIsNone(self.stocked_xy.current_layout_id)


class WarehouseCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="wh_crud", email="wh_crud@test.local", password="TestPass123!@"
        )
        cls.division = Division.objects.create(
            name="CRUD Division", slug="crud-division",
            created_by=cls.user, updated_by=cls.user,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def _grant_topography(self):
        from django.contrib.auth.models import Permission

        self.user.user_permissions.add(
            Permission.objects.get(codename="can_manage_topography")
        )
        self.user = User.objects.get(pk=self.user.pk)  # drop the perm cache
        self.client.force_login(self.user)

    def test_create_page_provisions_the_intake_room(self):
        self._grant_topography()
        response = self.client.post(
            reverse("inventory_warehouse_create"),
            {
                "name": "Created Warehouse",
                "code": "WH-CREATED",
                "division_id": str(self.division.pk),
                "address": "1 Test Way",
            },
        )
        self.assertEqual(response.status_code, 302)
        warehouse = Warehouse.objects.get(code="WH-CREATED")
        self.assertTrue(
            Room.objects.filter(warehouse=warehouse, is_intake_room=True).exists()
        )

    def test_duplicate_code_is_reported_not_crashed(self):
        self._grant_topography()
        WarehouseFactory.create(
            name="First", code="WH-DUPE", division_id=self.division.pk, actor=self.user
        )
        response = self.client.post(
            reverse("inventory_warehouse_create"),
            {
                "name": "Second",
                "code": "WH-DUPE",
                "division_id": str(self.division.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Warehouse.objects.filter(code="WH-DUPE").count(), 1)

    def test_retire_is_a_soft_delete_and_is_reversible(self):
        self._grant_topography()
        warehouse = WarehouseFactory.create(
            name="Retire Me", code="WH-RETIRE",
            division_id=self.division.pk, actor=self.user,
        )
        url = reverse("inventory_warehouse_edit", kwargs={"pk": warehouse.pk})

        self.client.post(url, {"action": "retire"})
        warehouse.refresh_from_db()
        self.assertFalse(warehouse.is_active)
        self.assertTrue(Warehouse.objects.filter(pk=warehouse.pk).exists())

        self.client.post(url, {"action": "reactivate"})
        warehouse.refresh_from_db()
        self.assertTrue(warehouse.is_active)

    def test_retired_warehouse_is_hidden_by_default_and_listable_on_request(self):
        self._grant_topography()
        warehouse = WarehouseFactory.create(
            name="Hidden", code="WH-HIDDEN",
            division_id=self.division.pk, actor=self.user,
        )
        TopographyContext(warehouse.pk).deactivate_warehouse(actor=self.user)

        default = self.client.get(reverse("inventory_warehouse_index"))
        self.assertNotContains(default, "WH-HIDDEN")

        retired = self.client.get(
            reverse("inventory_warehouse_index"), {"show": "inactive"}
        )
        self.assertContains(retired, "WH-HIDDEN")

    def test_writes_require_the_topography_permission(self):
        response = self.client.post(
            reverse("inventory_warehouse_create"),
            {"name": "Nope", "code": "WH-NOPE", "division_id": str(self.division.pk)},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Warehouse.objects.filter(code="WH-NOPE").exists())


class LayoutBuilderViewTests(TestCase):
    """The `/layout/` builder route is where every manual mutation lives —
    the legacy `/storeroom/<id>/build` page's add-location, add-bin, and
    delete actions, re-homed onto the existing canonical route."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission

        cls.user = User.objects.create_user(
            username="builder", email="builder@test.local", password="TestPass123!@"
        )
        cls.user.user_permissions.add(
            Permission.objects.get(codename="can_manage_topography")
        )
        cls.division = Division.objects.create(
            name="Builder Division", slug="builder-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={"part_number": "PN-BUILD-01", "name": "Build Widget"},
            actor=cls.user,
        )

    def setUp(self):
        self.user = User.objects.get(pk=self.user.pk)
        self.client.force_login(self.user)
        self.warehouse = WarehouseFactory.create(
            name="Builder WH", code=f"WH-BUILD-{self.id()[-6:]}",
            division_id=self.division.pk, actor=self.user,
        )
        self.context = TopographyContext(self.warehouse.pk)
        self.room = self.context.add_room(room_name="Build Room", actor=self.user)
        self.url = reverse("inventory_room_layout", kwargs={"pk": self.room.pk})

    def test_add_location_accepts_the_legacy_hyphenated_code(self):
        self.client.post(self.url, {"action": "add_location", "display_code": "5-2"})
        self.assertTrue(
            self.room.room_locations.filter(display_code="0005-0002").exists()
        )

    def test_add_location_rejects_a_duplicate(self):
        self.client.post(self.url, {"action": "add_location", "display_code": "5-2"})
        self.client.post(self.url, {"action": "add_location", "display_code": "5-2"})
        self.assertEqual(self.room.room_locations.count(), 1)

    def test_retire_location_blocked_by_stock_leaves_it_active(self):
        location = self.context.add_room_location(
            room_id=self.room.pk, major_coord="1", minor_coord="1", actor=self.user
        )
        bin_ = self.context.add_storage_location(
            room_location_id=location.pk, atomic_coord="1", actor=self.user
        )
        StockLedgerManager.inject(
            warehouse=self.warehouse, room=self.room, storage_location=bin_,
            part=self.part, qty=Decimal("2"), actor=self.user,
        )
        self.client.post(
            self.url, {"action": "retire_location", "room_location_id": location.pk}
        )
        location.refresh_from_db()
        self.assertTrue(location.is_active)

    def test_add_and_retire_bin_round_trip(self):
        location = self.context.add_room_location(
            room_id=self.room.pk, major_coord="2", minor_coord="2", actor=self.user
        )
        bin_url = reverse(
            "inventory_room_location_layout", kwargs={"pk": location.pk}
        )
        self.client.post(bin_url, {"action": "add_bin", "atomic_coord": "7"})
        created = location.storage_locations.get(atomic_coord="0007")
        self.assertEqual(created.display_code, "0002-0002-0007")

        self.client.post(
            bin_url, {"action": "retire_bin", "storage_location_id": created.pk}
        )
        created.refresh_from_db()
        self.assertFalse(created.is_active)

    def test_builder_writes_require_the_topography_permission(self):
        other = User.objects.create_user(
            username="builder_nope", email="nope@test.local", password="TestPass123!@"
        )
        self.client.force_login(other)
        response = self.client.post(
            self.url, {"action": "add_location", "display_code": "9-9"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.room.room_locations.count(), 0)


class RoomRetirementTests(TestCase):
    """A retired room must stay reachable — `room_detail` deliberately 404s on
    an inactive room, so the edit page is the surface that loads it and the
    only place reactivation can happen."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Permission

        cls.user = User.objects.create_user(
            username="room_retire", email="room_retire@test.local",
            password="TestPass123!@",
        )
        cls.user.user_permissions.add(
            Permission.objects.get(codename="can_manage_topography")
        )
        cls.division = Division.objects.create(
            name="Retire Division", slug="retire-division",
            created_by=cls.user, updated_by=cls.user,
        )

    def setUp(self):
        self.user = User.objects.get(pk=self.user.pk)
        self.client.force_login(self.user)
        self.warehouse = WarehouseFactory.create(
            name="Retire WH", code="WH-ROOM-RETIRE",
            division_id=self.division.pk, actor=self.user,
        )
        self.context = TopographyContext(self.warehouse.pk)
        self.room = self.context.add_room(room_name="Spare Room", actor=self.user)
        self.url = reverse("inventory_room_edit", kwargs={"pk": self.room.pk})

    def test_retire_then_reactivate_round_trip(self):
        self.client.post(self.url, {"action": "retire"})
        self.room.refresh_from_db()
        self.assertFalse(self.room.is_active)

        # The detail page is gone while retired...
        detail = self.client.get(
            reverse("inventory_room_detail", kwargs={"pk": self.room.pk})
        )
        self.assertEqual(detail.status_code, 404)

        # ...but the edit page still loads it, and offers reactivation.
        edit = self.client.get(self.url)
        self.assertEqual(edit.status_code, 200)
        self.assertContains(edit, "Reactivate room")

        self.client.post(self.url, {"action": "reactivate"})
        self.room.refresh_from_db()
        self.assertTrue(self.room.is_active)

    def test_intake_room_cannot_be_retired(self):
        intake = self.warehouse.rooms.get(is_intake_room=True)
        self.client.post(
            reverse("inventory_room_edit", kwargs={"pk": intake.pk}),
            {"action": "retire"},
        )
        intake.refresh_from_db()
        self.assertTrue(intake.is_active)

    def test_room_holding_locations_cannot_be_retired(self):
        self.context.add_room_location(
            room_id=self.room.pk, major_coord="1", minor_coord="1", actor=self.user
        )
        self.client.post(self.url, {"action": "retire"})
        self.room.refresh_from_db()
        self.assertTrue(self.room.is_active)
