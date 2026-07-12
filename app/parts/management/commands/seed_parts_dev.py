"""seed_parts_dev — dev fixture contribution for the Part Definitions kit.

Builds 16 Parts through the real control layer (Factories/Managers), not raw
ORM inserts, so every business rule (base revision, auto-alias, thread
lazy-create) is exercised exactly as production code would. Four car-part
drivers (alternator, engine, starter, AC compressor) are fully exercised with
varied revision depth, multiple manufacturers, supplier items with distinct
MPNs, a few documents/comments, and manual NSN/legacy aliases. The other 12
parts are light (1-2 revisions, 0-1 supplier items).

Idempotent: get_or_create on part_number; safe to re-run.
"""

from __future__ import annotations

import base64
import datetime

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand

from app.administration.models import Domain
from app.events.models import ActivityThread
from app.parts.control_layer.factories.alias_factory import AliasFactory
from app.parts.control_layer.factories.part_factory import PartFactory
from app.parts.control_layer.factories.part_manufacturer_factory import (
    PartManufacturerFactory,
)
from app.parts.control_layer.factories.supplier_item_factory import SupplierItemFactory
from app.parts.control_layer.managers.part_image_manager import PartImageManager
from app.parts.control_layer.managers.part_revision_manager import PartRevisionManager
from app.parts.control_layer.managers.part_thread_manager import PartThreadManager
from app.parts.control_layer.thread_domain import (
    default_domain_id_for,
    ensure_default_domains,
)
from app.parts.control_layer.managers.supplier_vendor_revision_manager import (
    SupplierVendorRevisionManager,
)
from app.parts.models import AliasSource, Part, PartManufacturer, PartRevisionStatus

User = get_user_model()

# 1x1 transparent PNG — a real image so seeded gallery photos actually render.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

LIGHT_PARTS = [
    ("PN-2001", "Brake Pad Set", "component", "brakes"),
    ("PN-2002", "Radiator Hose", "component", "cooling"),
    ("PN-2003", "Oil Filter", "component", "engine"),
    ("PN-2004", "Spark Plug", "component", "engine"),
    ("PN-2005", "Timing Belt", "component", "engine"),
    ("PN-2006", "Water Pump", "component", "cooling"),
    ("PN-2007", "Cabin Air Filter", "component", "hvac"),
    ("PN-2008", "Headlight Assembly", "assembly", "electrical"),
    ("PN-2009", "Wiper Blade", "component", "exterior"),
    ("PN-2010", "Fuel Pump", "component", "fuel"),
    ("PN-2011", "Shock Absorber", "component", "suspension"),
    ("PN-2012", "Serpentine Belt", "component", "engine"),
]

DRIVERS = {
    "alternator": {
        "part_number": "PN-1001",
        "name": "Alternator Assembly",
        "part_type": "assembly",
        "category": "electrical",
        "revisions": [
            {"kind": "major", "major_name": "A", "summary": "Initial production release"},
            {"kind": "major", "major_name": "B", "summary": "Bearing redesign"},
            {"kind": "redline", "minor_name": "1", "summary": "Wiring harness clarification redline"},
        ],
        "manufacturers": [
            ("Bosch", "BSH-ALT-01"),
            ("Denso", "DNS-ALT-9981"),
        ],
        "manual_aliases": [("NSN", "5950-01-445-1234"), ("LEGACY", "OLD-ALT-77")],
    },
    "engine": {
        "part_number": "PN-1002",
        "name": "Engine, 4-Cylinder 2.0L",
        "part_type": "assembly",
        "category": "powertrain",
        "revisions": [
            {"kind": "major", "major_name": "A", "summary": "Initial design"},
            {"kind": "redline", "minor_name": "1", "summary": "Gasket spec correction"},
            {"kind": "redline", "minor_name": "2", "summary": "Torque spec correction"},
            {"kind": "major", "major_name": "B", "summary": "Direct-injection upgrade"},
            {"kind": "major", "major_name": "C", "summary": "Turbocharged variant"},
        ],
        "manufacturers": [
            ("Continental Powertrain", "CPT-ENG-2000"),
        ],
        "manual_aliases": [("NSN", "2815-01-552-9012")],
    },
    "starter": {
        "part_number": "PN-1003",
        "name": "Starter Motor",
        "part_type": "component",
        "category": "electrical",
        "revisions": [
            {"kind": "major", "major_name": "A", "summary": "Initial release"},
        ],
        "manufacturers": [
            ("Denso", "DNS-STR-450"),
            ("Bosch", "BSH-STR-77"),
        ],
        "manual_aliases": [("LEGACY", "OLD-STR-12")],
    },
    "ac_compressor": {
        "part_number": "PN-1004",
        "name": "AC Compressor",
        "part_type": "component",
        "category": "hvac",
        "revisions": [
            {"kind": "major", "major_name": "A", "summary": "Initial release"},
            {"kind": "redline", "minor_name": "1", "summary": "Redline on A — mounting bracket fix"},
            {"kind": "major", "major_name": "B", "summary": "Variable-displacement upgrade"},
        ],
        "manufacturers": [
            ("Sanden", "SND-AC-330"),
        ],
        "manual_aliases": [("NSN", "4130-01-678-4455")],
    },
}


class Command(BaseCommand):
    help = "Seed dev Part data (16 parts; 4 fully-exercised drivers) via the control layer."

    def handle(self, *args, **options):
        actor = User.objects.filter(username="generic_admin").first() or User.objects.first()
        if actor is None:
            self.stdout.write(
                self.style.WARNING(
                    "No user found — run dev_auth_groups/dev_users/dev_ownership "
                    "fixtures before seed_parts_dev."
                )
            )
            return

        # §1: ensure the per-variant default bootstrap domains exist, then seed
        # part threads under the "Activity Thread" (DOCUMENTATION) default —
        # self-documenting, and no longer dependent on ownership fixtures.
        ensure_default_domains()
        domain = Domain.objects.get(id=default_domain_id_for(ActivityThread))

        for key, spec in DRIVERS.items():
            self._seed_driver(key, spec, actor=actor, domain=domain)

        for part_number, name, part_type, category in LIGHT_PARTS:
            self._seed_light_part(part_number, name, part_type, category, actor=actor)

        self.stdout.write(self.style.SUCCESS("Parts dev seed complete."))

    def _seed_driver(self, key: str, spec: dict, *, actor, domain: Domain) -> None:
        part, created = self._get_or_create_part(
            spec["part_number"], spec["name"], spec["part_type"], spec["category"], actor
        )
        if not created:
            self.stdout.write(f"  Part {part.part_number} already exists, skipping.")
            return

        manager = PartRevisionManager(part, actor)
        # Base revision (1.0) was already created by PartFactory; apply the rest.
        for rev_spec in spec["revisions"]:
            if rev_spec is spec["revisions"][0]:
                # First entry represents the base major (already created as 1.0
                # by PartFactory) — just relabel it with the spec's major_name.
                base = part.revisions.order_by("major_revision_number", "minor_revision_number").first()
                if base is not None and rev_spec.get("major_name"):
                    base.major_revision_name = rev_spec["major_name"]
                    base.summary = rev_spec["summary"]
                    base.status = PartRevisionStatus.RELEASED
                    base.save(update_fields=["major_revision_name", "summary", "status"])
                continue
            if rev_spec["kind"] == "redline":
                manager.redline(minor_name=rev_spec.get("minor_name"), summary=rev_spec["summary"])
            else:
                manager.release_major(
                    major_name=rev_spec.get("major_name"),
                    summary=rev_spec["summary"],
                    status=PartRevisionStatus.RELEASED,
                )

        # A document + a comment on the current revision.
        current = (
            part.revisions.order_by("-major_revision_number", "-minor_revision_number").first()
        )
        if current is not None:
            thread_mgr = PartThreadManager(current, actor)
            thread_mgr.add_comment(
                f"Initial engineering notes for {part.part_number} rev "
                f"{current.major_revision_number}.{current.minor_revision_number}.",
                domain_id=domain.id,
            )
            thread_mgr.attach_document(
                SimpleUploadedFile(
                    f"{part.part_number}_drawing.txt",
                    b"placeholder engineering drawing content",
                    content_type="text/plain",
                ),
                domain_id=domain.id,
                caption="Engineering drawing",
            )

        # Part-level threads (decoupled from revisions): a base library document
        # and a gallery photo. The gallery add auto-selects the hero and logs a
        # backend audit comment on the gallery thread.
        PartThreadManager(part, actor, thread_attr="documents_thread").attach_document(
            SimpleUploadedFile(
                f"{part.part_number}_specification.txt",
                b"placeholder part specification / work instruction content",
                content_type="text/plain",
            ),
            domain_id=domain.id,
            caption="Part specification",
        )
        PartImageManager(part, actor).add(
            SimpleUploadedFile(
                f"{part.part_number}_model.png", _TINY_PNG, content_type="image/png"
            ),
            domain_id=domain.id,
            caption="Model photo",
        )

        # Manufacturers + supplier items (distinct MPNs).
        for mfr_name, mpn in spec["manufacturers"]:
            mfr, _ = PartManufacturer.objects.get_or_create(
                name=mfr_name,
                defaults={"is_active": True, "created_by": actor, "updated_by": actor},
            )
            from app.parts.models import SupplierItem

            if not SupplierItem.objects.filter(
                part_manufacturer=mfr, manufacturer_part_number=mpn
            ).exists():
                item = SupplierItemFactory.create(
                    data={
                        "part_manufacturer_id": mfr.id,
                        "internal_part_id": part.id,
                        "manufacturer_part_number": mpn,
                        "name": f"{spec['name']} ({mfr_name})",
                    },
                    actor=actor,
                )
                SupplierVendorRevisionManager(item.id, actor).record(
                    vendor_revision_id="v1",
                    note="Initial vendor revision on file.",
                    domain_id=domain.id,
                )

        # Manual aliases (NSN/legacy).
        for alias_type, value in spec["manual_aliases"]:
            AliasFactory.for_string(
                part, value, alias_type, source=AliasSource.MANUAL, actor=actor
            )

        self.stdout.write(self.style.SUCCESS(f"  Seeded driver part {part.part_number}."))

    def _seed_light_part(
        self, part_number: str, name: str, part_type: str, category: str, *, actor
    ) -> None:
        part, created = self._get_or_create_part(part_number, name, part_type, category, actor)
        if not created:
            return
        # ~half get a second (redline) revision for variety.
        if int(part_number[-1]) % 2 == 0:
            PartRevisionManager(part, actor).redline(
                minor_name="1", summary="Minor field correction"
            )
        self.stdout.write(f"  Seeded light part {part.part_number}.")

    @staticmethod
    def _get_or_create_part(
        part_number: str, name: str, part_type: str, category: str, actor
    ) -> tuple[Part, bool]:
        existing = Part.objects.filter(part_number=part_number).first()
        if existing is not None:
            return existing, False
        part = PartFactory.create(
            data={
                "part_number": part_number,
                "name": name,
                "part_type": part_type,
                "category": category,
            },
            actor=actor,
        )
        part.revisions.update(date_of_release=datetime.date(2024, 1, 1))
        return part, True
