"""A PO's Event mirrors the assets of the events behind its demands.

Covers the producer side too: maintenance and reservations must write the
AssetEvent join row, not just their own asset column, or there is nothing for
the PO to aggregate.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from app.administration.models import Domain
from app.administration.models.data_ownership.user_assignments.user_domains import (
    UserDomain,
)
from app.assets.control_layer.orchestrators.asset_creation_orchestrator import (
    AssetCreationOrchestrator,
)
from app.assets.models import Asset, AssetClass, AssetModel, Manufacturer
from app.events.control_layer.managers.asset_event_link_manager import (
    AssetEventLinkManager,
)
from app.events.models import AssetEvent
from app.events.models.event import EventType
from app.events.models.details.maintenance import MaintenanceDetail
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.factories.part_demand_factory import (
    PartDemandFactory,
)
from app.procurement.control_layer.factories.purchase_order_factory import (
    PurchaseOrderFactory,
)
from app.procurement.control_layer.managers.purchase_order_asset_link_manager import (
    PURCHASE_ORDER_ASSET_ROLE,
    PurchaseOrderAssetLinkManager,
)
from app.procurement.control_layer.managers.purchase_order_demand_link_manager import (
    PurchaseOrderDemandLinkManager,
)
from app.procurement.control_layer.managers.purchase_order_line_manager import (
    PurchaseOrderLineManager,
)
from app.procurement.models import DemandSourceModule, Vendor

User = get_user_model()


class PurchaseOrderAssetLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="po_asset_tester",
            email="po_asset@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="PO Asset Domain",
            slug="po-asset-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        UserDomain.objects.create(
            user=cls.user, domain=cls.domain, created_by=cls.user, updated_by=cls.user
        )

        cls.asset_class = AssetClass.objects.create(
            name="PO Asset Fleet", created_by=cls.user, updated_by=cls.user
        )
        manufacturer = Manufacturer.objects.create(
            name="Testco", created_by=cls.user, updated_by=cls.user
        )
        cls.model = AssetModel.objects.create(
            model_name="Hauler",
            version="2020",
            asset_class=cls.asset_class,
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.model.manufacturers.add(manufacturer)

        cls.asset_a = cls._asset("Excavator A", "SN-A")
        cls.asset_b = cls._asset("Excavator B", "SN-B")

        cls.part = PartFactory.create(
            data={
                "part_number": "PN-POASSET-01",
                "name": "Hydraulic Seal",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )
        cls.vendor = Vendor.objects.create(
            name="Seal Supply Co", created_by=cls.user, updated_by=cls.user
        )

    @classmethod
    def _asset(cls, name: str, serial: str) -> Asset:
        # Through the orchestrator, not Asset.objects.create — an Asset has
        # required documentation/gallery threads it builds for us.
        return AssetCreationOrchestrator.create(
            data={
                "name": name,
                "serial_number": serial,
                "domain_id": cls.domain.pk,
                "model_id": cls.model.pk,
                "status": "Active",
            },
            actor=cls.user,
        )

    def _event_for(self, asset: Asset, title: str) -> MaintenanceDetail:
        """A maintenance event that owns an asset, with its join row written —
        the shape MaintenanceFactory now produces."""
        event = MaintenanceDetail.objects.create(
            domain=self.domain,
            asset=asset,
            title=title,
            event_type=EventType.MAINTENANCE,
            event_start=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )
        AssetEventLinkManager.link(
            asset_id=asset.pk, event_id=event.pk, role="target", actor=self.user
        )
        return event

    def _demand_for(self, event, quantity="2"):
        return PartDemandFactory.create(
            part_id=self.part.pk,
            domain_id=self.domain.pk,
            quantity_requested=Decimal(quantity),
            source=DemandSourceModule.MAINTENANCE,
            event_id=event.pk,
            actor=self.user,
        )

    def _po_with_line(self):
        po = PurchaseOrderFactory.create(
            vendor_id=self.vendor.pk, domain_id=self.domain.pk, actor=self.user
        )
        line, _ = PurchaseOrderLineManager.add_line(
            purchase_order=po,
            part_id=self.part.pk,
            quantity_ordered=Decimal("50"),
            unit_cost=Decimal("12.00"),
            actor=self.user,
        )
        return po, line

    def _po_asset_ids(self, po) -> set[int]:
        return set(
            AssetEvent.objects.filter(
                event_id=po.event_id, role=PURCHASE_ORDER_ASSET_ROLE
            ).values_list("asset_id", flat=True)
        )

    # ── the aggregation itself ──────────────────────────────────────────────

    def test_allocating_a_demand_copies_its_events_asset_onto_the_po(self):
        po, line = self._po_with_line()
        demand = self._demand_for(self._event_for(self.asset_a, "Seal replacement"))

        PurchaseOrderDemandLinkManager.allocate(
            line=line, demand=demand, quantity_allocated=Decimal("2"), actor=self.user
        )

        self.assertEqual(self._po_asset_ids(po), {self.asset_a.pk})

    def test_two_demands_on_different_assets_both_land_on_the_po(self):
        po, line = self._po_with_line()
        for asset, title in ((self.asset_a, "Job A"), (self.asset_b, "Job B")):
            PurchaseOrderDemandLinkManager.allocate(
                line=line,
                demand=self._demand_for(self._event_for(asset, title)),
                quantity_allocated=Decimal("2"),
                actor=self.user,
            )

        self.assertEqual(self._po_asset_ids(po), {self.asset_a.pk, self.asset_b.pk})

    def test_two_demands_on_the_same_asset_produce_one_row(self):
        """The set is unique by asset, not one row per contributing demand."""
        po, line = self._po_with_line()
        for title in ("Job one", "Job two"):
            PurchaseOrderDemandLinkManager.allocate(
                line=line,
                demand=self._demand_for(self._event_for(self.asset_a, title)),
                quantity_allocated=Decimal("2"),
                actor=self.user,
            )

        self.assertEqual(
            AssetEvent.objects.filter(
                event_id=po.event_id, role=PURCHASE_ORDER_ASSET_ROLE
            ).count(),
            1,
        )

    def test_a_demand_with_no_event_contributes_nothing(self):
        po, line = self._po_with_line()
        demand = PartDemandFactory.create(
            part_id=self.part.pk,
            domain_id=self.domain.pk,
            quantity_requested=Decimal("3"),
            source=DemandSourceModule.PROCUREMENT,
            actor=self.user,
        )

        PurchaseOrderDemandLinkManager.allocate(
            line=line, demand=demand, quantity_allocated=Decimal("3"), actor=self.user
        )

        self.assertEqual(self._po_asset_ids(po), set())

    def test_refresh_never_deletes_another_producers_link(self):
        """sync_role is role-scoped: a maintenance "target" link that happens to
        sit on the PO's own event must survive a refresh that does not name it."""
        po, _ = self._po_with_line()
        AssetEventLinkManager.link(
            asset_id=self.asset_b.pk,
            event_id=po.event_id,
            role="target",
            actor=self.user,
        )

        PurchaseOrderAssetLinkManager.refresh(purchase_order=po, actor=self.user)

        self.assertTrue(
            AssetEvent.objects.filter(
                event_id=po.event_id, asset=self.asset_b, role="target"
            ).exists()
        )


class AssetEventLinkManagerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="link_tester", email="link@test.local", password="TestPass123!@"
        )
        cls.domain = Domain.objects.create(
            name="Link Domain",
            slug="link-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.asset_class = AssetClass.objects.create(
            name="Link Fleet", created_by=cls.user, updated_by=cls.user
        )
        cls.model = AssetModel.objects.create(
            model_name="Loader",
            version="2021",
            asset_class=cls.asset_class,
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.asset = cls._make_asset("Loader One")

    @classmethod
    def _make_asset(cls, name: str) -> Asset:
        return AssetCreationOrchestrator.create(
            data={
                "name": name,
                "serial_number": f"SN-{name.replace(' ', '-')}",
                "domain_id": cls.domain.pk,
                "model_id": cls.model.pk,
                "status": "Active",
            },
            actor=cls.user,
        )

    def _event(self, *, with_asset: bool):
        return MaintenanceDetail.objects.create(
            domain=self.domain,
            asset=self.asset if with_asset else None,
            title="Job",
            event_type=EventType.MAINTENANCE,
            event_start=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )

    def test_link_is_idempotent(self):
        event = self._event(with_asset=True)
        for _ in range(3):
            AssetEventLinkManager.link(
                asset_id=self.asset.pk, event_id=event.pk, role="target"
            )
        self.assertEqual(
            AssetEvent.objects.filter(asset=self.asset, event=event).count(), 1
        )

    def test_link_ignores_a_missing_asset_id(self):
        event = self._event(with_asset=False)
        self.assertIsNone(AssetEventLinkManager.link(asset_id=None, event_id=event.pk))
        self.assertEqual(AssetEvent.objects.filter(event=event).count(), 0)

    def test_sync_role_adds_and_removes_within_its_own_role(self):
        event = self._event(with_asset=False)
        other = self._make_asset("Loader Two")
        AssetEventLinkManager.sync_role(
            event_id=event.pk, asset_ids=[self.asset.pk], role="mine"
        )
        added, removed = AssetEventLinkManager.sync_role(
            event_id=event.pk, asset_ids=[other.pk], role="mine"
        )

        self.assertEqual((added, removed), (1, 1))
        self.assertEqual(
            set(
                AssetEvent.objects.filter(event=event, role="mine").values_list(
                    "asset_id", flat=True
                )
            ),
            {other.pk},
        )

    def test_asset_ids_for_events_falls_back_to_the_maintenance_column(self):
        """Historical maintenance rows predate the join row; the column still
        answers the question."""
        event = self._event(with_asset=True)
        self.assertEqual(AssetEvent.objects.filter(event=event).count(), 0)
        self.assertEqual(
            AssetEventLinkManager.asset_ids_for_events(event_ids=[event.pk]),
            {self.asset.pk},
        )
