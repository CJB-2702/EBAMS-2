from django.core.management.base import BaseCommand
from django.utils import timezone
from app.administration.models import Domain, User
from app.assets.models import Asset, AssetClass
from app.events.models import Event, EventType, EventStatus, EventPriority, AssetEvent
from app.events.models.details import (
    MaintenanceDetail,
    DispatchingDetail,
    InventoryDetail,
    AssetManagementDetail,
    AdministrationDetail,
)

class Command(BaseCommand):
    help = "Seed development events across all sub-applications with detail models and AssetEvent links."

    def handle(self, *args, **options):
        domain = Domain.objects.first()
        if not domain:
            self.stdout.write(self.style.WARNING("No domain found to attach events. Skipping events seed."))
            return

        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        assets = list(Asset.objects.all()[:3])
        asset_class = AssetClass.objects.first()

        self.stdout.write("Seeding domain events and detail proxy models...")

        # 1. Maintenance Event
        if not MaintenanceDetail.objects.exists():
            maint = MaintenanceDetail.objects.create(
                title="Scheduled 500-Hour Generator Overhaul",
                description="Routine 500-hour preventive maintenance overhaul including filter replacement and fluid analysis.",
                event_type=EventType.MAINTENANCE,
                status=EventStatus.IN_PROGRESS,
                priority=EventPriority.HIGH,
                domain=domain,
                created_by=admin_user,
                work_order_reference="WO-MT-2026-0801",
                maintenance_type="corrective",
                actual_billable_hours=4.5,
                assigned_user=admin_user,
            )
            if assets:
                AssetEvent.objects.get_or_create(asset=assets[0], event=maint, role="target")
            self.stdout.write(f"  ✓ Maintenance event created: {maint.title}")

        # 2. Dispatching Event
        if asset_class and not DispatchingDetail.objects.filter(event_type=EventType.DISPATCHING).exists():
            now = timezone.now()
            disp = DispatchingDetail.objects.create(
                title="Sector Alpha Emergency Equipment Dispatch",
                description="Rapid deployment of heavy excavator and support trailers to Sector Alpha for road clearing.",
                event_type=EventType.DISPATCHING,
                status=EventStatus.IN_PROGRESS,
                priority=EventPriority.HIGH,
                domain=domain,
                created_by=admin_user,
                requested_for=admin_user,
                requested_by=admin_user,
                desired_start=now,
                desired_end=now + timezone.timedelta(days=2),
                asset_class=asset_class,
                activity_location="Sector Alpha Field Base",
                workflow_status="completed",
                dispatch_scope="regional",
            )
            if assets:
                AssetEvent.objects.get_or_create(asset=assets[min(1, len(assets)-1)], event=disp, role="primary_unit")
            self.stdout.write(f"  ✓ Dispatching event created: {disp.title}")

        # 2b. Reservation Event
        if asset_class and not Event.objects.filter(event_type=EventType.RESERVATION).exists():
            now = timezone.now()
            res = DispatchingDetail.objects.create(
                title="Emergency Power Unit Forward Asset Reservation",
                description="Advance booking request for CAT-3512 Diesel Generator to provide backup power during planned sector substation maintenance.",
                event_type=EventType.RESERVATION,
                status=EventStatus.PLANNED,
                priority=EventPriority.MEDIUM,
                domain=domain,
                created_by=admin_user,
                requested_for=admin_user,
                requested_by=admin_user,
                desired_start=now + timezone.timedelta(days=1),
                desired_end=now + timezone.timedelta(days=4),
                asset_class=asset_class,
                activity_location="Sector Substation Yard",
                workflow_status="planned",
                dispatch_scope="local",
            )
            if assets:
                AssetEvent.objects.get_or_create(asset=assets[0], event=res, role="reserved_unit")
            self.stdout.write(f"  ✓ Reservation event created: {res.title}")

        # 3. Inventory / Parts Event
        if not InventoryDetail.objects.exists():
            inv = InventoryDetail.objects.create(
                title="Hydraulic Filter Kit Bulk Issue",
                description="Bulk inventory issuance of 12x Heavy Duty Hydraulic Filters for upcoming fleet servicing.",
                event_type=EventType.INVENTORY,
                status=EventStatus.COMPLETE,
                priority=EventPriority.MEDIUM,
                domain=domain,
                created_by=admin_user,
                item_category="Hydraulics & Filters",
                location_reference="Central Bay Storage - Bin B12",
            )
            if assets:
                AssetEvent.objects.get_or_create(asset=assets[0], event=inv, role="consumed_by")
            self.stdout.write(f"  ✓ Inventory event created: {inv.title}")

        # 4. Asset Management Event
        if not AssetManagementDetail.objects.exists():
            am = AssetManagementDetail.objects.create(
                title="Asset Re-commissioning & Security Transfer",
                description="Primary asset transferred to Northern Division jurisdiction following safety audit.",
                event_type=EventType.ASSET_MANAGEMENT,
                status=EventStatus.COMPLETE,
                priority=EventPriority.LOW,
                domain=domain,
                created_by=admin_user,
            )
            if assets:
                AssetEvent.objects.get_or_create(asset=assets[0], event=am, role="subject")
            self.stdout.write(f"  ✓ Asset Management event created: {am.title}")

        # 5. Administration Event
        if not AdministrationDetail.objects.exists():
            adm = AdministrationDetail.objects.create(
                title="Domain Security Clearance Escalation",
                description="Granted Maintenance Lead role & domain write privileges for Northern Division to user Marcus Vance.",
                event_type=EventType.ADMINISTRATION,
                status=EventStatus.COMPLETE,
                priority=EventPriority.HIGH,
                domain=domain,
                created_by=admin_user,
            )
            self.stdout.write(f"  ✓ Administration event created: {adm.title}")

        self.stdout.write(self.style.SUCCESS("Finished seeding dev events."))
