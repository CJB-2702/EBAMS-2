"""Narrator: provenance and staleness phrasing for price observations.

One place that turns an observation into words, so the PO line, the grid, and
the price history page never disagree — staleness phrasing especially is the
signal this whole kit exists to deliver.
"""

from __future__ import annotations

from datetime import date

_MONTH_DAYS = 30


class PartPriceNarrator:
    @staticmethod
    def describe_recorded(*, vendor_name: str, observed_at: date) -> str:
        return f"{vendor_name} quoted this {PartPriceNarrator.staleness(observed_at)}."

    @staticmethod
    def describe_verified(*, vendor_name: str, domain_name: str, observed_at: date) -> str:
        return (
            f"Established price from {vendor_name} — {domain_name}, "
            f"{PartPriceNarrator.staleness(observed_at)}."
        )

    @staticmethod
    def describe_absent(vendor_name: str) -> str:
        return f"No price on record for {vendor_name}."

    @staticmethod
    def staleness(observed_at: date | None) -> str:
        """"3 days ago", "14 months ago" — the number rounded to whichever
        unit reads most honestly, never a raw day count."""
        if observed_at is None:
            return "at an unknown time"

        age_days = (date.today() - observed_at).days
        if age_days < 0:
            return "in the future"
        if age_days == 0:
            return "today"
        if age_days < _MONTH_DAYS:
            return f"{age_days} day{'s' if age_days != 1 else ''} ago"

        age_months = age_days // _MONTH_DAYS
        if age_months < 24:
            return f"{age_months} month{'s' if age_months != 1 else ''} ago"

        age_years = age_days // 365
        return f"{age_years} year{'s' if age_years != 1 else ''} ago"
