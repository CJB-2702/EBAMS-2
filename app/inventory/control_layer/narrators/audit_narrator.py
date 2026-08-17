"""Narrator: `AuditSession`/`InventoryAuditLog` numbering plus human-readable
audit text. Numbering mirrors `MovementNarrator` — sequential per calendar
year, computed inside `select_for_update` so concurrent finalizes don't
collide.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.inventory.models.audit.audit_session import AuditSession
from app.inventory.models.audit.inventory_audit_log import InventoryAuditLog


class AuditNarrator:
    @classmethod
    def generate_session_number(cls) -> str:
        year = timezone.now().year
        prefix = f"AUD-{year}-"
        with transaction.atomic():
            last = (
                AuditSession.objects.select_for_update()
                .filter(session_number__startswith=prefix)
                .order_by("-session_number")
                .first()
            )
            next_seq = int(last.session_number[-5:]) + 1 if last else 1
        return f"{prefix}{next_seq:05d}"

    @classmethod
    def generate_log_number(cls) -> str:
        year = timezone.now().year
        prefix = f"LOG-{year}-"
        with transaction.atomic():
            last = (
                InventoryAuditLog.objects.select_for_update()
                .filter(audit_number__startswith=prefix)
                .order_by("-audit_number")
                .first()
            )
            next_seq = int(last.audit_number[-5:]) + 1 if last else 1
        return f"{prefix}{next_seq:05d}"

    @staticmethod
    def line_recorded(
        *, part_number: str, expected_qty: Decimal, counted_qty: Decimal, discrepancy_type: str
    ) -> str:
        return (
            f"{part_number}: expected {expected_qty}, counted {counted_qty} "
            f"({discrepancy_type})."
        )

    @staticmethod
    def session_finalized(
        *, session_number: str, matched: int, surplus: int, deficit: int
    ) -> str:
        return (
            f"Audit session {session_number} finalized — {matched} matched, "
            f"{surplus} surplus, {deficit} deficit line(s)."
        )

    @staticmethod
    def session_cancelled(*, session_number: str) -> str:
        return f"Audit session {session_number} cancelled — no variances applied."

    @staticmethod
    def inline_edit_recorded(
        *, part_number: str, previous_qty: Decimal, new_qty: Decimal
    ) -> str:
        return f"Inline edit: {part_number} {previous_qty} -> {new_qty}."
