"""Phase 1 acceptance tests: coordinate formatting, Intake Room provisioning
and protection, effective-domain algebra, and topography uniqueness.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from app.administration.models import Division, Domain
from app.administration.models.data_ownership.user_assignments.user_domains import (
    UserDomain,
)
from app.inventory.control_layer.adapters.coordinate_adaptor import (
    build_room_location_display_code,
    build_storage_location_display_code,
    format_xyz_coordinate,
)
from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.factories.room_location_factory import (
    RoomLocationFactory,
)
from app.inventory.control_layer.factories.storage_location_factory import (
    StorageLocationFactory,
)
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.guards.room_guard import RoomDomainPolicy, RoomPolicy
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.room_location import RoomLocation
from app.inventory.models.topography.storage_location import StorageLocation
from app.inventory.models.topography.warehouse import Warehouse

User = get_user_model()


class CoordinateAdaptorTests(TestCase):
    def test_short_numeric_input_is_zero_padded(self):
        self.assertEqual(format_xyz_coordinate("10"), "0010")
        self.assertEqual(format_xyz_coordinate("5"), "0005")

    def test_long_numeric_input_is_not_truncated(self):
        self.assertEqual(format_xyz_coordinate("12345"), "12345")

    def test_non_numeric_input_passes_through_unchanged(self):
        self.assertEqual(format_xyz_coordinate("AISLE-A12"), "AISLE-A12")
        self.assertEqual(format_xyz_coordinate("RACK-99999"), "RACK-99999")

    def test_blank_input_is_empty_string(self):
        self.assertEqual(format_xyz_coordinate(""), "")

    def test_room_location_display_code_joins_with_hyphens(self):
        self.assertEqual(
            build_room_location_display_code("0010", "0005"), "0010-0005"
        )

    def test_storage_location_display_code_appends_atomic(self):
        self.assertEqual(
            build_storage_location_display_code("0010-0005", "0001"), "0010-0005-0001"
        )


class WarehouseFactoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="topo_smoke", email="topo@test.local", password="TestPass123!@"
        )
        cls.division = Division.objects.create(
            name="Test Division", slug="test-division",
            created_by=cls.user, updated_by=cls.user,
        )

    def test_create_provisions_a_protected_intake_room(self):
        warehouse = WarehouseFactory.create(
            name="Test Warehouse", code="WH-TEST-01",
            division_id=self.division.pk, actor=self.user,
        )
        intake = warehouse.rooms.get(is_intake_room=True)
        self.assertEqual(intake.room_name, "Intake")
        self.assertFalse(intake.is_deletable)
        self.assertFalse(intake.is_renamable)

    def test_duplicate_code_is_rejected(self):
        WarehouseFactory.create(
            name="Test Warehouse", code="WH-DUP-01",
            division_id=self.division.pk, actor=self.user,
        )
        with self.assertRaises(InventoryValidationError):
            WarehouseFactory.create(
                name="Another Warehouse", code="WH-DUP-01",
                division_id=self.division.pk, actor=self.user,
            )


class RoomPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="room_policy_smoke", email="room_policy@test.local",
            password="TestPass123!@",
        )
        cls.division = Division.objects.create(
            name="RP Division", slug="rp-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="RP Warehouse", code="WH-RP-01",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.intake = cls.warehouse.rooms.get(is_intake_room=True)
        cls.racking = Room.objects.create(
            warehouse=cls.warehouse, room_name="Racking",
            created_by=cls.user, updated_by=cls.user,
        )

    def test_intake_room_rename_is_blocked(self):
        with self.assertRaises(InventoryValidationError):
            RoomPolicy.check_rename(room=self.intake)

    def test_intake_room_delete_is_blocked(self):
        with self.assertRaises(InventoryValidationError):
            RoomPolicy.check_delete(room=self.intake)

    def test_ordinary_room_rename_is_allowed(self):
        RoomPolicy.check_rename(room=self.racking)

    def test_ordinary_room_delete_is_allowed_when_empty(self):
        RoomPolicy.check_delete(room=self.racking)

    def test_room_with_storage_locations_cannot_be_deleted(self):
        RoomLocationFactory.create(
            room_id=self.racking.pk, major_coord="10", minor_coord="5", actor=self.user,
        )
        with self.assertRaises(InventoryValidationError):
            RoomPolicy.check_delete(room=self.racking)


class RoomDomainPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="domain_algebra_smoke", email="domain_algebra@test.local",
            password="TestPass123!@",
        )
        cls.covering_user = User.objects.create_user(
            username="domain_algebra_covering", email="covering@test.local",
            password="TestPass123!@",
        )
        cls.division = Division.objects.create(
            name="DA Division", slug="da-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.domain_a = Domain.objects.create(
            name="Domain A", slug="da-domain-a", created_by=cls.user, updated_by=cls.user,
        )
        cls.domain_b = Domain.objects.create(
            name="Domain B", slug="da-domain-b", created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="DA Warehouse", code="WH-DA-01", division_id=cls.division.pk,
            domain_ids=[cls.domain_a.pk, cls.domain_b.pk], actor=cls.user,
        )
        cls.room = Room.objects.create(
            warehouse=cls.warehouse, room_name="Scoped Room",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.room.excluded_domains.set([cls.domain_b.pk])

        UserDomain.objects.create(
            user=cls.covering_user, domain=cls.domain_a,
            created_by=cls.user, updated_by=cls.user,
        )

    def test_effective_domains_is_warehouse_minus_excluded(self):
        effective = RoomDomainPolicy.effective_domains(self.room)
        self.assertEqual(effective, {self.domain_a.pk})

    def test_user_with_membership_in_effective_domain_covers_room(self):
        self.assertTrue(RoomDomainPolicy.user_covers_room(self.covering_user, self.room))

    def test_user_without_any_domain_membership_does_not_cover_room(self):
        self.assertFalse(RoomDomainPolicy.user_covers_room(self.user, self.room))

    def test_room_with_no_effective_domains_is_open_to_everyone(self):
        open_room = Room.objects.create(
            warehouse=self.warehouse, room_name="Open Room",
            created_by=self.user, updated_by=self.user,
        )
        open_room.excluded_domains.set([self.domain_a.pk, self.domain_b.pk])
        self.assertTrue(RoomDomainPolicy.user_covers_room(self.user, open_room))


class TopographyUniquenessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="uniq_smoke", email="uniq@test.local", password="TestPass123!@"
        )
        cls.division = Division.objects.create(
            name="Uniq Division", slug="uniq-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="Uniq Warehouse", code="WH-UNIQ-01",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.room = Room.objects.create(
            warehouse=cls.warehouse, room_name="Racking",
            created_by=cls.user, updated_by=cls.user,
        )

    def test_duplicate_room_name_in_same_warehouse_raises(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Room.objects.create(
                    warehouse=self.warehouse, room_name="Racking",
                    created_by=self.user, updated_by=self.user,
                )

    def test_duplicate_room_location_coordinate_is_rejected_by_factory(self):
        RoomLocationFactory.create(
            room_id=self.room.pk, major_coord="10", minor_coord="5", actor=self.user,
        )
        with self.assertRaises(InventoryValidationError):
            RoomLocationFactory.create(
                room_id=self.room.pk, major_coord="10", minor_coord="5", actor=self.user,
            )

    def test_duplicate_room_location_coordinate_is_rejected_at_db_level(self):
        RoomLocation.objects.create(
            room=self.room, major_coord="0010", minor_coord="0005",
            display_code="0010-0005",
            created_by=self.user, updated_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RoomLocation.objects.create(
                    room=self.room, major_coord="0010", minor_coord="0005",
                    display_code="0010-0005",
                    created_by=self.user, updated_by=self.user,
                )

    def test_duplicate_storage_location_atomic_coord_is_rejected_by_factory(self):
        room_location = RoomLocationFactory.create(
            room_id=self.room.pk, major_coord="10", minor_coord="5", actor=self.user,
        )
        StorageLocationFactory.create(
            room_location_id=room_location.pk, atomic_coord="1", actor=self.user,
        )
        with self.assertRaises(InventoryValidationError):
            StorageLocationFactory.create(
                room_location_id=room_location.pk, atomic_coord="1", actor=self.user,
            )

    def test_duplicate_storage_location_atomic_coord_is_rejected_at_db_level(self):
        room_location = RoomLocation.objects.create(
            room=self.room, major_coord="0010", minor_coord="0005",
            display_code="0010-0005",
            created_by=self.user, updated_by=self.user,
        )
        StorageLocation.objects.create(
            room_location=room_location, atomic_coord="0001",
            display_code="0010-0005-0001",
            created_by=self.user, updated_by=self.user,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StorageLocation.objects.create(
                    room_location=room_location, atomic_coord="0001",
                    display_code="0010-0005-0001",
                    created_by=self.user, updated_by=self.user,
                )


class StorageLocationSearchEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="loc_search_smoke", email="loc_search@test.local", password="TestPass123!@",
            is_superuser=True, is_staff=True,
        )
        cls.division = Division.objects.create(
            name="Search Division", slug="search-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="Search Warehouse", code="WH-SRCH-01",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.room = Room.objects.create(
            warehouse=cls.warehouse, room_name="Main Racking",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.room_location = RoomLocation.objects.create(
            room=cls.room, major_coord="0001", minor_coord="0001",
            display_code="0001-0001",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.location_a = StorageLocation.objects.create(
            room_location=cls.room_location, atomic_coord="0001",
            display_code="A-SHELF-01",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.location_b = StorageLocation.objects.create(
            room_location=cls.room_location, atomic_coord="0002",
            display_code="B-SHELF-02",
            created_by=cls.user, updated_by=cls.user,
        )

    def test_search_returns_matching_locations(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("storage_location_search") + "?q=A-SHELF")
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-value="%d"' % self.location_a.pk, response.content.decode())
        self.assertNotIn('data-value="%d"' % self.location_b.pk, response.content.decode())

    def test_search_no_matches_returns_disabled_li(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("storage_location_search") + "?q=NONEXISTENT")
        self.assertEqual(response.status_code, 200)
        self.assertIn("No matching locations.", response.content.decode())

