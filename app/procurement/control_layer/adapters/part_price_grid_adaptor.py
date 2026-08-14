"""PartPriceGridAdaptor — the bulk observation grid POST -> bulk factory
input. Mirrors PartCreationWizardAdaptor's indexed-row shape.

A row with no unit_cost is dropped (mirrors the `if not mpn: continue`
pattern in the parts wizard adaptor) but its part_id is carried in
dropped_part_ids so the page can list what was skipped instead of silently
losing it. Batch header fields (vendor, domain, observed_at, source_type,
confidence, notes) apply to every surviving row.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date

from app.procurement.control_layer.factories.part_price_observation_bulk_factory import (
    PriceObservationInput,
)
from app.parts.control_layer.adapters.form_parsing import parse_int


@dataclass(frozen=True)
class ParsedGrid:
    rows: list[PriceObservationInput]
    dropped_part_ids: list[int]
    errors: list[str]


class PartPriceGridAdaptor:
    @staticmethod
    def from_post(post) -> ParsedGrid:
        vendor_id = parse_int(post.get("vendor_id"))
        domain_id = parse_int(post.get("domain_id"))
        observed_at = parse_date((post.get("observed_at") or "").strip()) or None
        source_type = (post.get("source_type") or "").strip()
        confidence = (post.get("confidence") or "").strip()
        record_as_verified = post.get("record_as_verified") in ("on", "true", "1")
        header_notes = (post.get("notes") or "").strip()

        count = parse_int(post.get("row_count")) or 0
        rows: list[PriceObservationInput] = []
        dropped_part_ids: list[int] = []
        errors: list[str] = []

        for i in range(count):
            prefix = f"rows-{i}-"
            part_id = parse_int(post.get(f"{prefix}part_id"))
            if part_id is None:
                continue

            raw_cost = (post.get(f"{prefix}unit_cost") or "").strip()
            if not raw_cost:
                dropped_part_ids.append(part_id)
                continue

            unit_cost = PartPriceGridAdaptor._parse_money(raw_cost)
            if unit_cost is None:
                errors.append(f"Row {i + 1}: '{raw_cost}' is not a valid cost.")
                continue

            raw_quantity = (post.get(f"{prefix}quantity") or "").strip()
            quantity = (
                PartPriceGridAdaptor._parse_money(raw_quantity)
                if raw_quantity
                else None
            )

            rows.append(
                PriceObservationInput(
                    part_id=part_id,
                    vendor_id=vendor_id,
                    domain_id=domain_id,
                    unit_cost=unit_cost,
                    quantity=quantity,
                    observed_at=observed_at,
                    source_type=source_type,
                    confidence=confidence,
                    is_verified=record_as_verified,
                    notes=header_notes,
                )
            )

        return ParsedGrid(rows=rows, dropped_part_ids=dropped_part_ids, errors=errors)

    @staticmethod
    def _parse_money(raw: str) -> Decimal | None:
        """Strip $, spaces, and thousands separators before Decimal(...). An
        unparseable value is an error, not a silent zero."""
        cleaned = raw.replace("$", "").replace(",", "").strip()
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None

    # ------------------------------------------------------------------ #
    # Session draft handoff — the adaptor validates a COMPLETE grid at
    # submit; a session tool (Phase 3) holds the INCOMPLETE one while the
    # user types, using this same dict shape.
    # ------------------------------------------------------------------ #

    @staticmethod
    def to_session(rows: list[PriceObservationInput]) -> dict:
        return {
            "rows": [
                {
                    "part_id": row.part_id,
                    "vendor_id": row.vendor_id,
                    "domain_id": row.domain_id,
                    "unit_cost": str(row.unit_cost),
                    "quantity": str(row.quantity) if row.quantity is not None else None,
                    "observed_at": row.observed_at.isoformat() if row.observed_at else None,
                    "source_type": row.source_type,
                    "confidence": row.confidence,
                    "is_verified": row.is_verified,
                    "notes": row.notes,
                }
                for row in rows
            ]
        }

    @staticmethod
    def from_session(raw: dict) -> list[PriceObservationInput]:
        rows = []
        for entry in raw.get("rows") or []:
            observed_at = parse_date(entry["observed_at"]) if entry.get("observed_at") else None
            quantity = (
                Decimal(entry["quantity"]) if entry.get("quantity") is not None else None
            )
            rows.append(
                PriceObservationInput(
                    part_id=entry["part_id"],
                    vendor_id=entry["vendor_id"],
                    domain_id=entry["domain_id"],
                    unit_cost=Decimal(entry["unit_cost"]),
                    quantity=quantity,
                    observed_at=observed_at,
                    source_type=entry.get("source_type", ""),
                    confidence=entry.get("confidence", ""),
                    is_verified=bool(entry.get("is_verified", False)),
                    notes=entry.get("notes", ""),
                )
            )
        return rows
