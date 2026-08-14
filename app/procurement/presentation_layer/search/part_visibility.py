"""The one canonical part-visibility predicate (build_plan.md §2.4).

Write once, import everywhere — a second copy is how one branch loses its
filter (§2 rule 4). Consulted by the pricing grid, the unpriced queue, the
price-history search, and the recent-part-creations breadcrumb's re-read.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from app.parts.models import Part


def visible_parts_qs(*, domain_ids: list[int]) -> QuerySet[Part]:
    """Parts this actor may see. D14: a part is global unless
    is_domain_limited, in which case it needs an active mapping into one of
    the actor's domains. An empty domain_ids list still returns global
    parts — that is correct and matches accessible_domain_ids' documented
    reading."""
    return Part.objects.filter(
        Q(is_domain_limited=False)
        | Q(
            domain_access_mappings__domain_id__in=domain_ids,
            domain_access_mappings__is_active=True,
        )
    ).distinct()
