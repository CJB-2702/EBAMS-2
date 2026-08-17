"""Search: demands allocatable to a given part.

The PO wizard's key read. ANNOTATES outstanding quantity rather than computing
it per row — the legacy get_po_lines_with_demands looped lines, built a context
per line, and issued several queries inside each, then resolved each demand's
origin on top.

`for_part` defaults to `purchasing_state` unset — attaching one demand to two
purchase orders is legal but unusual, so it isn't offered silently.
`include_linked=True` is the escape hatch the assignment tools' server-side
search uses.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, F, Q, QuerySet

from app.procurement.models import PURCHASING_STATE_UNSET, DemandState, PartDemand

#: States a demand can be in and still be worth buying for.
ALLOCATABLE_DEMAND_STATES = frozenset(
    {DemandState.PROJECTED, DemandState.REQUIRED, DemandState.APPROVED}
)

#: The status dropdown on both left-heavy assignment components — a narrowed
#: view of DemandState.choices, since nothing outside ALLOCATABLE_DEMAND_STATES
#: is ever offered for allocation in the first place.
ALLOCATABLE_DEMAND_STATE_CHOICES = [
    (value, label)
    for value, label in DemandState.choices
    if value in ALLOCATABLE_DEMAND_STATES
]


class OpenDemandSearch:
    @classmethod
    def for_part(
        cls,
        *,
        part_id: int,
        domain_ids=None,
        exclude_purchase_order=None,
        exclude_ids=(),
        include_fully_allocated: bool = False,
        include_linked: bool = False,
        demand_id: int | None = None,
        demand_state: str = "",
        created_from=None,
        created_to=None,
        po_status: str = "",
    ) -> QuerySet[PartDemand]:
        """Demands the Buyer may allocate to a line buying this part.

        Defaults to `purchasing_state` unset — a demand already claimed by
        another PO does not show up here unless `include_linked=True` asks for
        it explicitly. Attaching one demand to more than one PO is legal but
        unusual, so the assignment tools gate that choice behind a warning
        rather than mixing it into the everyday pool silently.

        Ordered by priority then needed_by — the Buyer's queue order (D44).
        """
        qs = (
            PartDemand.objects.filter(
                part_id=part_id,
                demand_state__in=ALLOCATABLE_DEMAND_STATES,
                deleted_at__isnull=True,
            )
            .select_related("part", "domain")
            .annotate(
                outstanding_qty=F("quantity_requested") - F("purchased_qty"),
            )
        )

        # Domain scoping is applied here when the caller supplies the user's
        # domains. Enforcement is the presentation layer's job in this build;
        # this parameter is the seam it will use.
        if domain_ids is not None:
            qs = qs.filter(domain_id__in=domain_ids)

        if not include_fully_allocated:
            qs = qs.filter(outstanding_qty__gt=Decimal("0"))

        if not include_linked:
            qs = qs.filter(purchasing_state=PURCHASING_STATE_UNSET)

        if exclude_purchase_order is not None:
            # Demands already on this PO are not offered again — allocating
            # more means editing the existing row, not adding a second.
            qs = qs.exclude(
                allocations__purchase_order_line__purchase_order=exclude_purchase_order,
                allocations__deleted_at__isnull=True,
            )
        if exclude_ids:
            qs = qs.exclude(pk__in=exclude_ids)
        if demand_id:
            qs = qs.filter(pk=demand_id)
        if demand_state:
            qs = qs.filter(demand_state=demand_state)
        if created_from:
            qs = qs.filter(created_at__gte=created_from)
        if created_to:
            qs = qs.filter(created_at__lte=created_to)
        if po_status:
            # Only meaningful once `include_linked` has widened the pool —
            # a demand's linked PO(s), not the demand itself, carry this
            # status. `.distinct()` because a demand can be split across
            # more than one PO line.
            qs = qs.filter(
                allocations__is_active=True,
                allocations__deleted_at__isnull=True,
                allocations__purchase_order_line__purchase_order__status=po_status,
            ).distinct()

        return qs.order_by(
            cls._priority_ordering(), F("needed_by").asc(nulls_last=True)
        )

    @classmethod
    def pool(
        cls,
        *,
        domain_ids,
        part_id: int | None = None,
        q: str = "",
        priority: str = "",
        needed_before=None,
        created_from=None,
        created_to=None,
        requested_by: str = "",
        linked_po_number: str = "",
        exclude_purchase_order=None,
        include_fully_allocated: bool = False,
    ) -> QuerySet[PartDemand]:
        """The wizard's "from demands" tab: the same allocatable pool as
        `for_part`, but across every part, with the filter row's parameters.

        `domain_ids` is REQUIRED here rather than optional. `for_part` predates
        any caller and left the fence optional; a cross-part pool that forgot it
        would show a Buyer every open demand in the organization, so this entry
        point does not offer that mistake.

        `linked_po_number` is the "find it by the OTHER order" escape hatch — a
        demand already allocated (in full or in part) to some other PO is still
        a legitimate candidate here (D28 allows splitting one demand across
        POs), so this filter widens the pool to fully-allocated rows rather than
        requiring `include_fully_allocated` to be passed alongside it. The cap
        decision dialog is what actually stops an over-allocation; the search
        should not pre-empt it by hiding the demand.
        """
        qs = (
            PartDemand.objects.filter(
                demand_state__in=ALLOCATABLE_DEMAND_STATES,
                domain_id__in=domain_ids,
                deleted_at__isnull=True,
            )
            .select_related("part", "domain", "requested_by")
            .annotate(outstanding_qty=F("quantity_requested") - F("purchased_qty"))
        )

        if part_id:
            qs = qs.filter(part_id=part_id)
        if q:
            qs = qs.filter(
                Q(part__part_number__icontains=q)
                | Q(part__name__icontains=q)
                | Q(notes__icontains=q)
            )
        if priority:
            qs = qs.filter(priority=priority)
        if needed_before:
            qs = qs.filter(needed_by__lte=needed_before)
        if created_from:
            qs = qs.filter(created_at__gte=created_from)
        if created_to:
            qs = qs.filter(created_at__lte=created_to)
        if requested_by:
            qs = qs.filter(
                Q(requested_by__username__icontains=requested_by)
                | Q(requested_by__first_name__icontains=requested_by)
                | Q(requested_by__last_name__icontains=requested_by)
            )
        if exclude_purchase_order is not None:
            qs = qs.exclude(
                allocations__purchase_order_line__purchase_order=exclude_purchase_order,
                allocations__deleted_at__isnull=True,
            )
        if linked_po_number:
            qs = qs.filter(
                allocations__is_active=True,
                allocations__deleted_at__isnull=True,
                allocations__purchase_order_line__purchase_order__po_number__icontains=(
                    linked_po_number
                ),
            ).distinct()
        elif not include_fully_allocated:
            qs = qs.filter(outstanding_qty__gt=Decimal("0"))

        return qs.order_by(
            cls._priority_ordering(), F("needed_by").asc(nulls_last=True)
        )

    @classmethod
    def index_list(
        cls,
        *,
        domain_ids,
        demand_state: str = "",
        purchasing_state: str = "",
        shipment_state: str = "",
        issuance_state: str = "",
        priority: str = "",
        part_id: int | None = None,
        domain_id: int | None = None,
        needed_by_from=None,
        needed_by_to=None,
        created_from=None,
        created_to=None,
        requested_by: str = "",
        po_number: str = "",
        q: str = "",
    ) -> QuerySet[PartDemand]:
        """The demand_index page (part_demand_workflows.md §2.1) — one canonical
        list, not three: the Approver's queue is this with
        `demand_state=required`, the Buyer's "what needs buying" view is this
        with a sparse `purchasing_state` filter.

        Unlike `pool`/`for_part`, this is NOT restricted to
        ALLOCATABLE_DEMAND_STATES — the list must also show Rejected,
        Cancelled, and Completed demands when a filter or the unfiltered
        default asks for them. `domain_ids` is required, same reasoning as
        `pool`: a list that forgot the fence would leak cross-domain rows.

        Default sort is priority then needed_by (D44) — never "newest first".
        """
        qs = (
            PartDemand.objects.filter(
                domain_id__in=domain_ids, deleted_at__isnull=True
            )
            .select_related("part", "domain", "requested_by")
            .annotate(outstanding_qty=F("quantity_requested") - F("purchased_qty"))
        )

        if demand_state:
            qs = qs.filter(demand_state=demand_state)
        if purchasing_state:
            qs = qs.filter(purchasing_state=purchasing_state)
        if shipment_state:
            qs = qs.filter(shipment_state=shipment_state)
        if issuance_state:
            qs = qs.filter(issuance_state=issuance_state)
        if priority:
            qs = qs.filter(priority=priority)
        if part_id:
            qs = qs.filter(part_id=part_id)
        if domain_id:
            qs = qs.filter(domain_id=domain_id)
        if needed_by_from:
            qs = qs.filter(needed_by__gte=needed_by_from)
        if needed_by_to:
            qs = qs.filter(needed_by__lte=needed_by_to)
        if created_from:
            qs = qs.filter(created_at__gte=created_from)
        if created_to:
            qs = qs.filter(created_at__lte=created_to)
        if requested_by:
            if str(requested_by).isdigit():
                qs = qs.filter(requested_by_id=int(requested_by))
            else:
                qs = qs.filter(
                    Q(requested_by__username__icontains=requested_by)
                    | Q(requested_by__first_name__icontains=requested_by)
                    | Q(requested_by__last_name__icontains=requested_by)
                )
        if po_number:
            qs = qs.filter(
                allocations__is_active=True,
                allocations__deleted_at__isnull=True,
                allocations__purchase_order_line__purchase_order__po_number__icontains=po_number,
            ).distinct()
        if q:
            qs = qs.filter(
                Q(part__part_number__icontains=q)
                | Q(part__name__icontains=q)
                | Q(notes__icontains=q)
            )

        return qs.order_by(
            cls._priority_ordering(), F("needed_by").asc(nulls_last=True)
        )

    @staticmethod
    def _priority_ordering():
        """Critical first. Priority is a CharField of choices, so sort by an
        explicit rank rather than alphabetically."""
        from django.db.models import Case, IntegerField, Value, When

        from app.procurement.models import DemandPriority

        return Case(
            When(priority=DemandPriority.CRITICAL, then=Value(0)),
            When(priority=DemandPriority.HIGH, then=Value(1)),
            When(priority=DemandPriority.MEDIUM, then=Value(2)),
            When(priority=DemandPriority.LOW, then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        ).asc()
