"""Manager: asset-limitation sub-domain for one MaintenanceDetail
(MaintenanceContext.limitation_manager).

Owns AssetLimitationRecord creation/close and keeps Asset.capability_status in
sync — the worst active limitation across ALL maintenance events for that
asset wins, not just the one being edited (a degraded status opened from a
different event must still show up here).
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from app.assets.models.core.asset import Asset
from app.maintenance.models.asset_limitation import AssetLimitationRecord, CapabilityStatus

#: worst-to-best ranking; lowest number wins when multiple limitations are active.
STATUS_PRIORITY = {
    CapabilityStatus.NON_CAPABLE: 1,
    CapabilityStatus.FUNCTIONAL_LIMITATIONS: 2,
    CapabilityStatus.TEMPORARY_COMPENSATION: 3,
    CapabilityStatus.FULLY_CAPABLE_COMPENSATION: 4,
}

_COMPENSATION_STATUSES = frozenset(
    {CapabilityStatus.TEMPORARY_COMPENSATION, CapabilityStatus.FULLY_CAPABLE_COMPENSATION}
)
_DEGRADED_STATUSES = frozenset(
    {CapabilityStatus.NON_CAPABLE, CapabilityStatus.FUNCTIONAL_LIMITATIONS}
)


class AssetLimitationManager:
    def __init__(self, maintenance_context) -> None:
        self._ctx = maintenance_context

    @staticmethod
    def _validate_modification_rules(*, status: str, temporary_modifications: str) -> None:
        """Compensation statuses REQUIRE a description of the compensation;
        degraded statuses FORBID one — a caller cannot claim a workaround exists
        for a status that says the asset simply cannot do the job."""
        has_modifications = bool(temporary_modifications and temporary_modifications.strip())
        if status in _COMPENSATION_STATUSES and not has_modifications:
            raise ValueError(
                f"Status '{status}' requires temporary modifications describing "
                "the compensation in place."
            )
        if status in _DEGRADED_STATUSES and has_modifications:
            raise ValueError(
                f"Status '{status}' cannot carry temporary modifications — only "
                "compensation statuses can."
            )

    def create_record(
        self,
        *,
        status: str,
        limitation_description: str = "",
        temporary_modifications: str = "",
        start_time=None,
        maintenance_blocker_id: int | None = None,
        actor=None,
    ) -> AssetLimitationRecord:
        if self._ctx.struct.active_limitation_records:
            raise ValueError(
                "An active limitation record already exists. Close it before "
                "opening another."
            )
        self._validate_modification_rules(
            status=status, temporary_modifications=temporary_modifications
        )
        with transaction.atomic():
            record = AssetLimitationRecord.objects.create(
                maintenance_detail=self._ctx.maintenance_detail,
                status=status,
                limitation_description=limitation_description,
                temporary_modifications=temporary_modifications,
                start_time=start_time or timezone.now(),
                maintenance_blocker_id=maintenance_blocker_id,
                created_by=actor,
                updated_by=actor,
            )
            self.refresh_capability_status(asset_id=self._ctx.maintenance_detail.asset_id)
        self._ctx.refresh()
        return record

    def update_record(self, *, record_id: int, actor=None, **fields) -> AssetLimitationRecord:
        record = AssetLimitationRecord.objects.get(
            pk=record_id, maintenance_detail_id=self._ctx.maintenance_detail_id
        )
        final_status = fields.get("status", record.status)
        final_modifications = fields.get(
            "temporary_modifications", record.temporary_modifications
        )
        self._validate_modification_rules(
            status=final_status, temporary_modifications=final_modifications
        )
        with transaction.atomic():
            update_fields: list[str] = []
            for field_name in ("status", "limitation_description", "temporary_modifications"):
                if field_name in fields and fields[field_name] is not None:
                    setattr(record, field_name, fields[field_name])
                    update_fields.append(field_name)
            if update_fields:
                record.updated_by = actor
                update_fields += ["updated_by", "updated_at"]
                record.save(update_fields=update_fields)
            self.refresh_capability_status(asset_id=self._ctx.maintenance_detail.asset_id)
        self._ctx.refresh()
        return record

    def close_record(self, *, record_id: int, end_time=None, actor=None) -> AssetLimitationRecord:
        record = AssetLimitationRecord.objects.get(
            pk=record_id, maintenance_detail_id=self._ctx.maintenance_detail_id
        )
        if record.end_time is not None:
            raise ValueError(f"Record {record_id} is already closed.")
        final_end_time = end_time or timezone.now()
        if record.start_time > final_end_time:
            raise ValueError("Start time cannot be after end time.")
        with transaction.atomic():
            record.end_time = final_end_time
            record.updated_by = actor
            record.save(update_fields=["end_time", "updated_by", "updated_at"])
            self.refresh_capability_status(asset_id=self._ctx.maintenance_detail.asset_id)
        self._ctx.refresh()
        return record

    @classmethod
    def refresh_capability_status(cls, *, asset_id: int | None) -> str | None:
        """Recompute Asset.capability_status as the worst active limitation across
        every maintenance event for this asset."""
        if asset_id is None:
            return None
        active_statuses = list(
            AssetLimitationRecord.objects.filter(
                maintenance_detail__asset_id=asset_id,
                end_time__isnull=True,
                deleted_at__isnull=True,
            ).values_list("status", flat=True)
        )
        worst_status = (
            min(active_statuses, key=lambda s: STATUS_PRIORITY.get(s, 999))
            if active_statuses
            else None
        )
        Asset.objects.filter(pk=asset_id).update(capability_status=worst_status)
        return worst_status
