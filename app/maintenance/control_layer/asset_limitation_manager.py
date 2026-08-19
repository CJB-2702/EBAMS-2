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


class AssetLimitationNarrator:
    """Narrator: machine-written activity-log sentences for limitations."""

    @staticmethod
    def created(*, actor, status: str) -> str:
        who = getattr(actor, "username", None) or "system"
        return f"Asset capability limitation opened by {who}: {status}."

    @staticmethod
    def closed(*, actor, status: str, resolution_notes: str) -> str:
        who = getattr(actor, "username", None) or "system"
        return f"Asset capability limitation ({status}) closed by {who}: {resolution_notes}"


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
        link_to_active_blocker: bool = False,
        comment: str = "",
        actor=None,
    ) -> AssetLimitationRecord:
        """Open a limitation.

        `link_to_active_blocker` resolves the event's current active blocker
        and hangs this record off it. The FK has existed on the model since
        the first pass with nothing ever setting it — the link is what lets a
        reader tell "the asset is degraded AND that is why work stopped" from
        "the asset is degraded, and separately work stopped for some other
        reason". Those are different situations and the FK is the only thing
        that distinguishes them.

        An explicit `maintenance_blocker_id` wins over the flag, so a caller
        that already knows which blocker it means is never second-guessed.
        """
        if status not in CapabilityStatus.values:
            raise ValueError(
                f"'{status}' is not a valid capability status. "
                f"Choose one of: {', '.join(CapabilityStatus.values)}."
            )
        if self._ctx.struct.active_limitation_records:
            raise ValueError(
                "An active limitation record already exists. Close it before "
                "opening another."
            )
        self._validate_modification_rules(
            status=status, temporary_modifications=temporary_modifications
        )

        if maintenance_blocker_id is None and link_to_active_blocker:
            active = self._ctx.struct.active_blockers
            if not active:
                raise ValueError(
                    "There is no active blocker to link this limitation to."
                )
            maintenance_blocker_id = active[0].pk

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

        self._narrate(
            comment=comment,
            fallback=AssetLimitationNarrator.created(actor=actor, status=status),
            actor=actor,
        )
        self._ctx.refresh()
        return record

    def _narrate(self, *, comment: str, fallback: str, actor) -> None:
        """Activity-log entry for a limitation transition. Outside the
        transaction on purpose — a failed comment must not lose the record."""
        text = (comment or "").strip()
        self._ctx.add_comment(
            {"content": text or fallback},
            actor=actor,
            is_human_made=bool(text),
        )

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

    def close_record(
        self,
        *,
        record_id: int,
        resolution_notes: str,
        start_time=None,
        end_time=None,
        comment: str = "",
        actor=None,
    ) -> AssetLimitationRecord:
        """Close a limitation — the close-out form, matching legacy's.

        `start_time` and `end_time` are both editable here because a
        limitation is routinely recorded after the fact: the asset was
        degraded from Tuesday morning, but somebody opened the record on
        Wednesday. Closing is the moment the true window is known.

        `resolution_notes` is mandatory. Closing asserts the asset can do the
        thing again, and that assertion propagates to Asset.capability_status
        where other people act on it — it needs a stated reason.
        """
        if not (resolution_notes or "").strip():
            raise ValueError("A resolution note is required to close a limitation.")

        record = AssetLimitationRecord.objects.get(
            pk=record_id, maintenance_detail_id=self._ctx.maintenance_detail_id
        )
        if record.end_time is not None:
            raise ValueError(f"Record {record_id} is already closed.")

        final_start_time = start_time or record.start_time
        final_end_time = end_time or timezone.now()
        if final_start_time > final_end_time:
            raise ValueError("Start time cannot be after end time.")
        with transaction.atomic():
            record.start_time = final_start_time
            record.end_time = final_end_time
            record.resolution_notes = resolution_notes.strip()
            record.updated_by = actor
            record.save(
                update_fields=[
                    "start_time", "end_time", "resolution_notes",
                    "updated_by", "updated_at",
                ]
            )
            self.refresh_capability_status(asset_id=self._ctx.maintenance_detail.asset_id)

        self._narrate(
            comment=comment,
            fallback=AssetLimitationNarrator.closed(
                actor=actor, status=record.status, resolution_notes=resolution_notes
            ),
            actor=actor,
        )
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
