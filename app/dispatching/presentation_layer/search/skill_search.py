"""Read helpers for the skills catalogue — typeahead for requirement pickers
(dispatch and template manifests) and the catalogue list screen."""

from __future__ import annotations

from django.db.models import QuerySet

from app.dispatching.models.skills.dispatch_skill import DispatchSkill


def search_skills(
    *, q: str = "", active_only: bool = True, exclude_certified_for_user_id: int | None = None
) -> QuerySet[DispatchSkill]:
    qs = DispatchSkill.objects.order_by("name")
    if active_only:
        qs = qs.filter(is_active=True)
    if exclude_certified_for_user_id is not None:
        # certify() rejects ANY existing row for the pair, active or revoked
        # (the DB unique constraint is unconditional) — the picker must not
        # offer a skill the person already has a record for.
        qs = qs.exclude(user_certifications__user_id=exclude_certified_for_user_id)

    q = (q or "").strip()
    if q:
        qs = qs.filter(name__icontains=q)

    return qs
