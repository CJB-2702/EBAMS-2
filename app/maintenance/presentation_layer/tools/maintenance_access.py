"""Presentation-layer access helpers for the maintenance app.

Mirrors app.procurement.presentation_layer.tools.procurement_access's shape
(domain fence + boolean gates), but the maintenance starter kit's P3
capability matrix does not name specific Django permission codenames the way
the procurement Phase 0 plan did. Rather than invent permission codenames
that no migration declares, every write here is gated on plain
"is this user in the record's domain" (D5) plus an authenticated session.
This is intentionally coarser than procurement's per-verb permission system —
flagged in the porting summary as a follow-up for the Admin persona once
role/permission templates for Maintenance are decided.
"""

from __future__ import annotations

from django.http import HttpRequest

from app.administration.auth_session import session_domain_ids


def accessible_domain_ids(request: HttpRequest) -> list[int]:
    """The user's data domains, snapshotted at login (D5, P4)."""
    return session_domain_ids(request)


def is_in_domain(request: HttpRequest, domain_id: int | None) -> bool:
    if domain_id is None:
        return False
    return domain_id in accessible_domain_ids(request)
