"""Manager: barcode parsing and the algorithmic scan-matching engine
(`control_layer_map.md` §3, `sequence_diagrams.md` workflows 2-5, FD-13's
Phase 5 scope).

`parse_barcode` turns a raw scanner payload into `(sku, serial)`.
`find_target_line` resolves a scanned part to exactly one open shipment line
when the match is unambiguous (1-to-1); ambiguous (N-to-M) or unmatched scans
land staged (`shipment_line=NULL`) instead. `execute_fifo_cascade` re-links a
part's staged pool onto its open lines, oldest line first, whenever the
staged total is enough to fully satisfy at least one more line.
`validate_serial_uniqueness` is a thin wrapper over
`AllocationValidator.check_composite_sn_unique` — Phase 2's `StockValidator`
duplicate check is already folded into that guard method, which checks both
live allocations and `ActiveInventory`, so this manager delegates rather than
re-implementing it (per the phase file's original, since-corrected framing).
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum

from app.inventory.control_layer.errors import BarcodeParseError
from app.inventory.control_layer.guards.intake_guard import AllocationValidator
from app.inventory.models.intake.enums import AllocationCondition
from app.inventory.models.intake.intake_session import IntakeSession
from app.inventory.models.intake.item_allocation import ItemAllocation

# ASCII Group Separator — the FNC1 delimiter most GS1-128 scanners emit
# between variable-length Application Identifier fields.
_FNC1 = "\x1d"

# Bracketed GS1-128 notation, e.g. "(01)00012345678905(21)SN00042" — a
# common human-readable rendering used by label-printing software and some
# scanner drivers configured to wrap each AI in parentheses.
_GS1_BRACKETED_RE = re.compile(r"\((\d{2,4})\)([^\(]+)")

# Plain 1D SKU, optionally suffixed with this house convention for a
# serial: "SKU;SERIAL". Bare alphanumeric/dash/dot/underscore tokens only —
# anything else is presumed not to be a hand-typed or Code128/Code39 SKU.
_PLAIN_SKU_RE = re.compile(r"[A-Za-z0-9\-_.]+")
_SKU_SERIAL_DELIMITER = ";"


class IntakeMatchingManager:
    @classmethod
    def parse_barcode(cls, raw_payload: str) -> tuple[str, str]:
        """Parse a scanned payload into `(sku, serial)`. Serial is `""` when
        the payload carries none. Tries three formats, in order:

        1. GS1-128 bracketed AI notation — `(01)<gtin>(21)<serial>`. AI 01
           (GTIN/SKU) and AI 21 (serial) are read; any other AIs present are
           parsed but ignored.
        2. GS1-128 raw digit stream (no brackets) — `01` + exactly 14 GTIN
           digits, optionally followed by `21` + a variable-length serial
           terminated by an FNC1 (`\\x1d`) separator or end of string.
        3. Plain 1D SKU, optionally suffixed `;SERIAL` (house convention).
           A bare SKU with no delimiter returns an empty serial.

        Anything matching none of the above raises `BarcodeParseError`
        rather than crashing the scan request — `IntakeContext.process_scan`
        lets it propagate (it is already an `InventoryValidationError`
        subtype) so the scan portal can fall back to manual entry.
        """
        payload = (raw_payload or "").strip()
        if not payload:
            raise BarcodeParseError(raw_payload=raw_payload)

        parsed = (
            cls._parse_gs1_bracketed(payload)
            or cls._parse_gs1_raw(payload)
            or cls._parse_plain(payload)
        )
        if parsed is None:
            raise BarcodeParseError(raw_payload=raw_payload)
        return parsed

    @classmethod
    def _parse_gs1_bracketed(cls, payload: str) -> tuple[str, str] | None:
        if "(" not in payload:
            return None
        matches = _GS1_BRACKETED_RE.findall(payload)
        if not matches:
            return None
        ai_values = {ai: value.strip() for ai, value in matches}
        sku = ai_values.get("01")
        if not sku:
            return None
        return sku, ai_values.get("21", "")

    @classmethod
    def _parse_gs1_raw(cls, payload: str) -> tuple[str, str] | None:
        cleaned = payload.lstrip(_FNC1)
        if not cleaned.startswith("01") or len(cleaned) < 16 or not cleaned[2:16].isdigit():
            return None
        sku = cleaned[2:16]
        remainder = cleaned[16:]
        if not remainder:
            return sku, ""
        if not remainder.startswith("21"):
            # Trailing content that isn't a recognized AI — not confidently
            # parseable as GS1-128; let the caller try the plain-SKU path.
            return None
        rest = remainder[2:]
        cut = rest.find(_FNC1)
        serial = (rest[:cut] if cut != -1 else rest).strip()
        return sku, serial

    @classmethod
    def _parse_plain(cls, payload: str) -> tuple[str, str] | None:
        if _SKU_SERIAL_DELIMITER in payload:
            sku, serial = payload.split(_SKU_SERIAL_DELIMITER, 1)
        else:
            sku, serial = payload, ""
        if not _PLAIN_SKU_RE.fullmatch(sku):
            return None
        if serial and not _PLAIN_SKU_RE.fullmatch(serial):
            return None
        return sku, serial

    # ------------------------------------------------------------------ #
    # Matching
    # ------------------------------------------------------------------ #

    @classmethod
    def find_target_line(cls, *, session: IntakeSession, part):
        """Among this session's linked shipments' open lines for `part`
        (expected > allocated+rejected so far in this session — same
        aggregation `ReconciliationManager.generate_tasks` uses), return the
        one candidate line if the match is unambiguous. Zero or multiple
        candidates return `None` (ambiguous N-to-M, or no match at all) —
        the caller stages the allocation with `shipment_line=NULL` instead.
        """
        from app.procurement.models import ShipmentLine

        linked_shipment_ids = list(
            session.shipment_associations.filter(deleted_at__isnull=True).values_list(
                "shipment_id", flat=True
            )
        )
        if not linked_shipment_ids:
            return None

        candidate_lines = ShipmentLine.objects.filter(
            shipment_id__in=linked_shipment_ids, part_id=part.pk, deleted_at__isnull=True
        )

        open_lines = [
            line
            for line in candidate_lines
            if cls._remaining_quantity(session=session, line=line) > 0
        ]
        if len(open_lines) == 1:
            return open_lines[0]
        return None

    @classmethod
    def execute_fifo_cascade(cls, *, session: IntakeSession, part) -> None:
        """Atomically re-link this session's staged (`shipment_line=NULL`,
        `condition=GOOD`) allocations for `part` onto the session's open
        lines for `part`, oldest shipment line first (`id` order), filling
        each line's remaining expected quantity before moving to the next.
        Only re-links a line once the staged pool can fully satisfy it —
        per the spec, cascading happens "when staged totals cross a line's
        expected quantity." Any leftover un-fillable remainder stays staged.
        """
        from app.procurement.models import ShipmentLine

        linked_shipment_ids = list(
            session.shipment_associations.filter(deleted_at__isnull=True).values_list(
                "shipment_id", flat=True
            )
        )
        if not linked_shipment_ids:
            return

        with transaction.atomic():
            open_lines = list(
                ShipmentLine.objects.filter(
                    shipment_id__in=linked_shipment_ids,
                    part_id=part.pk,
                    deleted_at__isnull=True,
                ).order_by("id")
            )
            if not open_lines:
                return

            remaining_by_line_id = {}
            for line in open_lines:
                remaining = cls._remaining_quantity(session=session, line=line)
                if remaining > 0:
                    remaining_by_line_id[line.pk] = remaining
            if not remaining_by_line_id:
                return

            staged_rows = list(
                ItemAllocation.objects.select_for_update()
                .filter(
                    intake_session=session,
                    part_id=part.pk,
                    shipment_line__isnull=True,
                    condition=AllocationCondition.GOOD,
                    deleted_at__isnull=True,
                )
                .order_by("id")
            )
            total_staged = sum((row.quantity for row in staged_rows), Decimal("0"))
            if total_staged <= 0:
                return

            for line in open_lines:
                remaining = remaining_by_line_id.get(line.pk)
                if remaining is None:
                    continue
                if total_staged < remaining:
                    # FIFO order — this (and every later) line can't be
                    # fully satisfied yet. Stop; leave the pool staged.
                    break

                to_fill = remaining
                while to_fill > 0 and staged_rows:
                    row = staged_rows[0]
                    if row.quantity <= to_fill:
                        row.shipment_line = line
                        row.save(update_fields=["shipment_line", "updated_at"])
                        to_fill -= row.quantity
                        staged_rows.pop(0)
                    else:
                        leftover = row.quantity - to_fill
                        ItemAllocation.objects.create(
                            intake_session=session,
                            shipment_line=line,
                            part_id=part.pk,
                            quantity=to_fill,
                            serial_number=row.serial_number,
                            composite_sn=row.composite_sn,
                            condition=row.condition,
                            intake_method=row.intake_method,
                            created_by=row.created_by,
                            updated_by=row.updated_by,
                        )
                        row.quantity = leftover
                        row.save(update_fields=["quantity", "updated_at"])
                        to_fill = Decimal("0")
                total_staged -= remaining

    @classmethod
    def _remaining_quantity(cls, *, session: IntakeSession, line) -> Decimal:
        totals = ItemAllocation.objects.filter(
            intake_session=session, shipment_line=line, deleted_at__isnull=True
        ).aggregate(
            good=Sum("quantity", filter=Q(condition=AllocationCondition.GOOD)),
            rejected=Sum("quantity", filter=Q(condition=AllocationCondition.REJECTED)),
        )
        allocated = (totals["good"] or Decimal("0")) + (totals["rejected"] or Decimal("0"))
        return line.quantity - allocated

    # ------------------------------------------------------------------ #
    # Serial uniqueness
    # ------------------------------------------------------------------ #

    @classmethod
    def validate_serial_uniqueness(
        cls, *, part_id: int, serial_number: str, session_id: int | None = None
    ) -> None:
        """Delegates to `AllocationValidator.check_composite_sn_unique`,
        which already checks both live `ItemAllocation` rows (across every
        session, not just `session_id`) and live `ActiveInventory` — the
        same composite-serial check Phase 2's `StockValidator` pattern
        establishes. `session_id` is accepted for call-site symmetry with
        the kit's spec but is not used to narrow the check: a serial in use
        anywhere is a duplicate everywhere.
        """
        AllocationValidator.check_composite_sn_unique(
            part_id=part_id, serial_number=serial_number
        )
