"""Tests for `TopographyContext.upload_room_layout` /
`upload_room_location_layout`: reconciliation correctness (matched /
unmatched / orphaned) and that only sanitized SVG is ever archived
(FD-23/FD-25/FD-29).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from app.administration.models import Division
from app.inventory.control_layer.factories.room_location_factory import RoomLocationFactory
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.topography_context import TopographyContext
from app.inventory.models.topography.room import Room

User = get_user_model()

ROOM_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="200" height="200">
  <script>alert(1)</script>
  <g inkscape:label="locations">
    <rect inkscape:label="0005-0002" x="0" y="0" width="10" height="10" />
    <rect inkscape:label="0001-0001" x="20" y="20" width="10" height="10" />
  </g>
</svg>"""

BINS_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="100" height="100">
  <g inkscape:label="bins">
    <rect inkscape:label="0001" x="0" y="0" width="10" height="10" />
    <rect inkscape:label="0002" x="10" y="0" width="10" height="10" />
  </g>
</svg>"""


class RoomLayoutUploadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="svg_upload_smoke", email="svg_upload@test.local",
            password="TestPass123!@",
        )
        cls.division = Division.objects.create(
            name="SVG Division", slug="svg-division",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.warehouse = WarehouseFactory.create(
            name="SVG Warehouse", code="WH-SVG-01",
            division_id=cls.division.pk, actor=cls.user,
        )
        cls.room = Room.objects.create(
            warehouse=cls.warehouse, room_name="Racking",
            created_by=cls.user, updated_by=cls.user,
        )
        # One pre-existing RoomLocation that the new SVG will NOT reference —
        # exercises the "orphaned" bucket.
        cls.orphan = RoomLocationFactory.create(
            room_id=cls.room.pk, major_coord="0009", minor_coord="0009", actor=cls.user,
        )
        # One pre-existing RoomLocation the new SVG DOES reference —
        # exercises the "matched" bucket.
        cls.existing = RoomLocationFactory.create(
            room_id=cls.room.pk, major_coord="0005", minor_coord="0002", actor=cls.user,
        )

    def test_reconciliation_buckets_are_correct(self):
        context = TopographyContext(self.warehouse.pk)
        upload = SimpleUploadedFile("room.svg", ROOM_SVG, content_type="image/svg+xml")
        result = context.upload_room_layout(
            room_id=self.room.pk, uploaded_file=upload, actor=self.user
        )
        self.assertEqual(result.matched, ("0005-0002",))
        self.assertEqual(result.unmatched_shapes, ("0001-0001",))
        self.assertEqual(result.orphaned, ("0009-0009",))

    def test_upload_archives_sanitized_svg_as_current_layout(self):
        context = TopographyContext(self.warehouse.pk)
        upload = SimpleUploadedFile("room.svg", ROOM_SVG, content_type="image/svg+xml")
        context.upload_room_layout(
            room_id=self.room.pk, uploaded_file=upload, actor=self.user
        )
        self.room.refresh_from_db()
        self.assertIsNotNone(self.room.current_layout_id)
        stored = self.room.current_layout.file.file.read().decode("utf-8")
        self.assertNotIn("<script", stored)
        self.assertIn("0005-0002", stored)

    def test_upload_never_deletes_or_creates_room_locations(self):
        context = TopographyContext(self.warehouse.pk)
        upload = SimpleUploadedFile("room.svg", ROOM_SVG, content_type="image/svg+xml")
        before = set(self.room.room_locations.values_list("display_code", flat=True))
        context.upload_room_layout(
            room_id=self.room.pk, uploaded_file=upload, actor=self.user
        )
        after = set(self.room.room_locations.values_list("display_code", flat=True))
        self.assertEqual(before, after)

    def test_room_location_tier_upload_reconciles_against_atomic_coords(self):
        context = TopographyContext(self.warehouse.pk)
        context.add_storage_location(
            room_location_id=self.existing.pk, atomic_coord="0001", actor=self.user
        )
        upload = SimpleUploadedFile("bins.svg", BINS_SVG, content_type="image/svg+xml")
        result = context.upload_room_location_layout(
            room_location_id=self.existing.pk, uploaded_file=upload, actor=self.user
        )
        self.assertEqual(result.matched, ("0001",))
        self.assertEqual(result.unmatched_shapes, ("0002",))
        self.assertEqual(result.orphaned, ())
