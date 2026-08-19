"""Search: domain-scoped QuerySet filters for the maintenance part-demand queue.

Legacy: presentation/routes/maintenance/user_views/manager/part_demands.py.

Every query starts from procurement.PartDemand — the hub (G3) — and reaches
maintenance context *outward* through MaintenanceDemandLink, never the other
way (D7). That link table is what supplies the Action / Event / Asset columns
the legacy queue showed; demands raised by Dispatching or General have no link
row and legitimately render blank in those columns, exactly as the legacy page
rendered them ``N/A``.

Two scopes, because the legacy page conflated them and the conflation was
useful: MAINTENANCE (has a link row — the queue a maintenance manager actually
works) and ALL (every demand in the user's domains, which is what the legacy
page really showed).
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from app.procurement.models import PartDemand

#: ``scope=`` values. Not a model enum — this is a presentation-layer view
#: choice over one queryset, not a stored attribute of anything.
SCOPE_MAINTENANCE = "maintenance"
SCOPE_ALL = "all"
SCOPE_CHOICES = (
    (SCOPE_MAINTENANCE, "Maintenance demands only"),
    (SCOPE_ALL, "All demands in my domains"),
)


class MaintenanceDemandSearch:
    @classmethod
    def index_list(
        cls,
        *,
        domain_ids,
        scope: str = SCOPE_MAINTENANCE,
        demand_state: str = "",
        issuance_state: str = "",
        purchasing_state: str = "",
        priority: str = "",
        part_id: int | None = None,
        q: str = "",
        event_id: int | None = None,
        asset_id: int | None = None,
        event_status: str = "",
        assigned_user_id: int | None = None,
        created_from=None,
        created_to=None,
        updated_from=None,
        updated_to=None,
        sort: str = "",
    ) -> QuerySet[PartDemand]:
        """The part_demand_index page. One canonical list — the approval queue
        is `?demand_state=required`, "what's still outstanding" is
        `?issuance_state=not_issued`. No saved presets."""
        qs = PartDemand.objects.filter(
            domain_id__in=domain_ids, deleted_at__isnull=True
        ).select_related("part", "domain", "requested_by")

        if scope == SCOPE_MAINTENANCE:
            qs = qs.filter(pk__in=cls._maintenance_linked_ids())

        if demand_state:
            qs = qs.filter(demand_state=demand_state)
        if issuance_state:
            qs = qs.filter(issuance_state=issuance_state)
        if purchasing_state:
            qs = qs.filter(purchasing_state=purchasing_state)
        if priority:
            qs = qs.filter(priority=priority)
        if part_id:
            qs = qs.filter(part_id=part_id)
        if q:
            qs = qs.filter(
                Q(part__part_number__icontains=q)
                | Q(part__name__icontains=q)
                | Q(notes__icontains=q)
            )

        # ── The collapsed "Maintenance Event Filters" tier ──────────────────
        # Each of these traverses the link table outward. They are meaningful
        # only for demands that have one, so any of them implies the
        # maintenance scope whether or not the user selected it.
        if event_id:
            qs = qs.filter(maintenance_links__action__event_detail_id=event_id)
        if asset_id:
            qs = qs.filter(maintenance_links__action__event_detail__asset_id=asset_id)
        if event_status:
            qs = qs.filter(maintenance_links__action__event_detail__status=event_status)
        if assigned_user_id:
            qs = qs.filter(
                maintenance_links__action__event_detail__assigned_user_id=assigned_user_id
            )
        if event_id or asset_id or event_status or assigned_user_id:
            qs = qs.distinct()

        if created_from:
            qs = qs.filter(created_at__gte=created_from)
        if created_to:
            qs = qs.filter(created_at__lte=created_to)
        if updated_from:
            qs = qs.filter(updated_at__gte=updated_from)
        if updated_to:
            qs = qs.filter(updated_at__lte=updated_to)

        return qs.order_by(*cls._ordering(sort))

    @staticmethod
    def _maintenance_linked_ids():
        """Demand ids carrying at least one live maintenance link.

        A subquery, NOT ``filter(maintenance_links__deleted_at__isnull=True)``.
        Django promotes a reverse-relation join to LEFT OUTER when the
        condition is ``__isnull=True``, so that spelling matches demands with
        NO link row at all — their NULLs satisfy the IS NULL test — which is
        the exact opposite of what this scope means.
        """
        from app.maintenance.models.demand_link import MaintenanceDemandLink

        return MaintenanceDemandLink.objects.filter(
            deleted_at__isnull=True, action__deleted_at__isnull=True
        ).values("part_demand_id")

    #: `sort=` -> order_by args. Whitelisted rather than passed through to
    #: order_by, which would let a query string name any column or traverse
    #: any relation.
    _SORTS: dict[str, tuple[str, ...]] = {
        "": ("-created_at",),
        "created_desc": ("-created_at",),
        "created_asc": ("created_at",),
        "updated_desc": ("-updated_at",),
        "part": ("part__part_number", "-created_at"),
        "quantity_desc": ("-quantity_requested",),
        "state": ("demand_state", "-created_at"),
    }

    @classmethod
    def _ordering(cls, sort: str) -> tuple[str, ...]:
        return cls._SORTS.get(sort, cls._SORTS[""])

    @classmethod
    def maintenance_context_for(cls, demand_ids) -> dict[int, dict]:
        """One query for the Action / Event / Asset columns of a whole page.

        Returned per demand id rather than annotated onto the queryset because
        a demand may carry more than one link row (the same part needed by two
        steps of one job); the queue shows the first, and the detail page shows
        them all.
        """
        from app.maintenance.models.demand_link import MaintenanceDemandLink

        rows = (
            MaintenanceDemandLink.objects.filter(
                part_demand_id__in=list(demand_ids),
                deleted_at__isnull=True,
                action__deleted_at__isnull=True,
            )
            .select_related(
                "action",
                "action__event_detail",
                "action__event_detail__asset",
                "action__event_detail__assigned_user",
            )
            .order_by("part_demand_id", "sequence_order")
        )

        context: dict[int, dict] = {}
        for link in rows:
            entry = context.setdefault(
                link.part_demand_id,
                {"links": [], "action": None, "event": None, "asset": None},
            )
            entry["links"].append(link)
            if entry["action"] is None:
                event = link.action.event_detail
                entry["action"] = link.action
                entry["event"] = event
                entry["asset"] = event.asset if event else None
        return context
