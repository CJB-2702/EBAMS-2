"""Factory: creates a Package and its lines with copied PO links."""

from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone

from app.events.models import Event, EventStatus, EventType
from app.procurement.control_layer.managers.package_line_manager import (
    PackageLineManager,
)
from app.procurement.control_layer.managers.package_status_manager import (
    PackageStatusManager,
)
from app.procurement.control_layer.narrators.package_narrator import PackageNarrator
from app.procurement.models import Package, PackageStatus


class PackageFactory:
    @classmethod
    def generate_package_number(cls) -> str:
        today = timezone.now().date().isoformat()
        return f"PKG-{today}-{uuid.uuid4().hex[:8]}"

    @classmethod
    def create(
        cls,
        *,
        domain=None,
        purchase_order=None,
        lines: list[dict] | None = None,
        actor=None,
        shipment_id: str = "",
        carrier: str = "",
        shipped_date=None,
        expected_arrival_date=None,
        notes: str = "",
        status: str = PackageStatus.AWAITING_SHIPMENT,
    ) -> Package:
        """A package is created against a purchase order OR received
        reactively with none yet on file (D71/D73 reverses D59's "never
        free-floating" rule).

        ``domain`` is required when ``purchase_order`` is None — a package
        cannot exist without SOME domain to fence it. When a PO is supplied,
        its domain is copied and an explicit ``domain`` must either be omitted
        or agree with it.

        Each line dict is {"part_id": int, "quantity": Decimal}. Lines copy
        their PO link from the header automatically; a line whose part matches
        no active line on the header PO is recorded with a null PO line rather
        than refused.
        """
        if purchase_order is not None:
            domain = domain or purchase_order.domain
        if domain is None:
            raise ValueError(
                "PackageFactory.create requires a domain when no purchase_order "
                "is supplied."
            )

        with transaction.atomic():
            package_number = cls.generate_package_number()

            event = Event.objects.create(
                domain_id=domain.pk,
                title=f"Package {package_number}",
                description=notes,
                event_type=EventType.INVENTORY,
                status=EventStatus.IN_PROGRESS,
                created_by=actor,
                updated_by=actor,
            )

            package = Package.objects.create(
                purchase_order=purchase_order,
                domain=domain,
                event=event,
                package_number=package_number,
                shipment_id=shipment_id,
                carrier=carrier,
                status=status,
                shipped_date=shipped_date,
                expected_arrival_date=expected_arrival_date,
                notes=notes,
                created_by=actor,
                updated_by=actor,
            )

            for raw_line in lines or []:
                PackageLineManager.add_line(
                    package=package,
                    part_id=raw_line["part_id"],
                    quantity=raw_line["quantity"],
                    actor=actor,
                    commit=False,
                )

            PackageStatusManager.refresh_mixed_po_assignments(
                package=package, actor=actor, commit=True
            )
            PackageStatusManager.propagate_shipment_state(
                package=package, actor=actor
            )

            PackageNarrator.post(
                package=package,
                message=PackageNarrator.created(
                    package_number=package.package_number,
                    line_count=len(lines or []),
                    purchase_order_number=(
                        purchase_order.po_number if purchase_order else ""
                    ),
                ),
                actor=actor,
            )

        return package
