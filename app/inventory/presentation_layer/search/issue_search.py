"""Search: the issues ledger list (`/inventory/issues`)."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from app.inventory.models.issuance.part_issue import PartIssue
from app.inventory.presentation_layer.search.active_inventory_search import (
    domain_visible_room_ids,
)


class IssueSearch:
    @classmethod
    def index_list(
        cls,
        *,
        domain_ids,
        issue_type: str = "",
        part_q: str = "",
        demand_id: str = "",
    ) -> QuerySet[PartIssue]:
        visible_room_ids = domain_visible_room_ids(domain_ids=domain_ids)
        qs = PartIssue.objects.filter(
            Q(from_room_id__in=visible_room_ids)
            | Q(from_room__isnull=True)
        ).select_related(
            "part_demand",
            "part_demand__part",
            "issued_to",
            "issued_to_asset",
            "from_room",
            "from_room__warehouse",
            "from_storage_location",
        )

        if issue_type:
            qs = qs.filter(issue_type=issue_type)
        if part_q:
            qs = qs.filter(
                Q(part_demand__part__part_number__icontains=part_q)
                | Q(part_demand__part__name__icontains=part_q)
            )
        if demand_id:
            qs = qs.filter(part_demand_id=demand_id)

        return qs.order_by("-issued_at")
