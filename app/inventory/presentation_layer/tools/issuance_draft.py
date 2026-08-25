"""The issuance queue — the staged receipt behind `/inventory/issue-parts/`.

DEMAND FIRST. A queue line is always anchored to a real `PartDemand`; stock is
the easy half, filled in afterwards from the bins holding that demand's part.
The portal is not, and must not become, a stock browser that lets you go
hunting for a demand to hang a balance on — an inventory-first workflow is a
separate portal for a later kit, not a second mode bolted onto this one.

That rules out three shapes this module used to support:

  * staging a bare stock balance (`/inventory/active-inventory/`'s bulk
    "Queue for Part Issuance" action, now removed),
  * ad-hoc demands described in a popup and materialised at commit — a demand
    is raised in procurement, not invented at the counter,
  * a per-line recipient. The receipt has ONE recipient, on its header.

So a line is now just: which demand, which balance, how many.

    {"demand_id": 412, "active_inventory_id": 88, "quantity": "4.000", "notes": ""}

A DEMAND MAY APPEAR ON SEVERAL LINES, deliberately. Two things make that the
ordinary case rather than an exception:

  * the container runs dry mid-handover and the rest comes off another shelf,
  * serialised parts. `ActiveInventory` holds ONE ROW PER SERIAL (its
    uniqueness is `(room, storage_location, part, serial_number)` and a
    serialised row is capped at qty 1), so three specific serials is three
    lines of one unit each. There is no other way to express it.

State lives in `request.session` under a per-user key. That is the right home
BECAUSE THIS IS A RECEIPT, NOT A PREPARATORY SESSION: there is no walk-the-
floor gap, no reservation, and no handing the queue to another operator, so
nothing here needs to be a row until the parts actually change hands. Contrast
`IntakeSession`, which is genuinely preparatory and earns its table.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.http import HttpRequest

from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.presentation_layer.search.active_inventory_search import (
    domain_visible_room_ids,
)
from app.procurement.models import PartDemand

#: Same key shape the pre-extraction code used, so a session mid-build at
#: deploy time keeps its queue rather than silently losing it.
SESSION_KEY_PREFIX = "issuance_draft_"

#: The demands on the plan, whether or not any stock has been pointed at them
#: yet. A SEPARATE list from the lines because staging a demand no longer
#: fabricates a bin-less line to hang it on: a line means "this much, off this
#: shelf", and one with no shelf is not a smaller version of that, it is a
#: different thing wearing the same shape. The plan is therefore
#: demands-with-lines-under-them, and a demand sitting at zero lines is a
#: legitimate, visible state.
DEMAND_KEY_PREFIX = "issuance_demands_"


def session_key(request: HttpRequest) -> str:
    return f"{SESSION_KEY_PREFIX}{request.user.pk}"


def load(request: HttpRequest) -> list[dict]:
    if not request.user.is_authenticated:
        return []
    return request.session.get(session_key(request), [])


def save(request: HttpRequest, lines: list[dict]) -> None:
    request.session[session_key(request)] = lines
    request.session.modified = True


def demand_key(request: HttpRequest) -> str:
    return f"{DEMAND_KEY_PREFIX}{request.user.pk}"


def load_demands(request: HttpRequest) -> list[int]:
    """Staged demand ids, in the order they were added."""
    if not request.user.is_authenticated:
        return []
    return request.session.get(demand_key(request), [])


def save_demands(request: HttpRequest, demand_ids: list[int]) -> None:
    request.session[demand_key(request)] = demand_ids
    request.session.modified = True


def clear(request: HttpRequest) -> None:
    save(request, [])
    save_demands(request, [])


def count(request: HttpRequest) -> int:
    """What the topnav badge shows: every line, plus every staged demand not
    yet pointed at any stock. Still just dict lookups — no database."""
    lines = load(request)
    with_lines = {l.get("demand_id") for l in lines}
    return len(lines) + sum(1 for d in load_demands(request) if d not in with_lines)


def remove_at(request: HttpRequest, index: int) -> bool:
    lines = load(request)
    if 0 <= index < len(lines):
        lines.pop(index)
        save(request, lines)
        return True
    return False


def remove_demand(request: HttpRequest, demand_id: int) -> int:
    """Drop a demand and every planned issuance staged under it.

    Whole-group removal, not N clicks on N lines: the lines exist only to
    answer that demand, so leaving them behind after removing it would leave
    the receipt holding stock nobody asked for.
    """
    lines = load(request)
    kept = [l for l in lines if l.get("demand_id") != demand_id]
    removed = len(lines) - len(kept)
    if removed:
        save(request, kept)

    demands = load_demands(request)
    if demand_id in demands:
        save_demands(request, [d for d in demands if d != demand_id])
        return removed or 1
    return removed


def to_decimal(raw) -> Decimal | None:
    raw = (raw or "").strip() if isinstance(raw, str) else raw
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None


def to_int(raw) -> int | None:
    if raw is None:
        return None
    raw = str(raw).strip()
    return int(raw) if raw.isdigit() else None


def new_line(
    *,
    demand_id: int,
    active_inventory_id: int | None = None,
    quantity: Decimal | str = "1.000",
    notes: str = "",
) -> dict:
    return {
        "demand_id": demand_id,
        "active_inventory_id": active_inventory_id,
        "quantity": str(quantity),
        "notes": notes or "",
    }


# --------------------------------------------------------------------------- #
# Staging
# --------------------------------------------------------------------------- #


def _only_matching_stock(part_id: int, *, domain_ids) -> ActiveInventory | None:
    """The auto-pick seam: the balance holding this part, but ONLY when there
    is exactly one of them.

    Two or more and this returns None on purpose. The predecessor took the
    "first" match, which meant every staged line arrived carrying a pairing
    the clerk still had to verify — a guess you always have to check is worse
    than a blank the clerk knows to fill. Note that a part with three serials
    on one shelf is three rows, so serialised parts almost never auto-pick,
    which is right: the clerk is hunting a specific serial anyway.
    """
    candidates = list(
        ActiveInventory.objects.filter(
            part_id=part_id,
            quantity_on_hand__gt=0,
            room_id__in=domain_visible_room_ids(domain_ids=domain_ids),
        ).select_related("part")[:2]
    )
    return candidates[0] if len(candidates) == 1 else None


def _staged_quantity_for(lines: list[dict], demand_id: int) -> Decimal:
    total = Decimal("0")
    for line in lines:
        if line.get("demand_id") == demand_id:
            total += to_decimal(line.get("quantity")) or Decimal("0")
    return total


def outstanding_for(demand, lines: list[dict]) -> Decimal:
    """What this demand still needs AFTER everything already on the plan.

    The ceiling on every quantity the plan will accept for it. A bin holding
    more than the demand asked for comes in at the demand's number, not the
    bin's: the plan is a promise to a requester, and over-issuing by default
    because a shelf happened to be full is not something anyone asked for.
    """
    remaining = (
        demand.quantity_requested
        - demand.issued_qty
        - _staged_quantity_for(lines, demand.pk)
    )
    return remaining if remaining > 0 else Decimal("0")


def add_demand_lines(
    request: HttpRequest, *, demand_ids, domain_ids
) -> tuple[int, int, int]:
    """Put demands on the plan, pointing one at stock only where the pairing
    is unambiguous.

    Returns (staged, paired, skipped). `paired` is a subset of `staged` — the
    ones that found exactly one balance holding their part.

    A DEMAND WITH NO OBVIOUS BIN STAGES WITH NO LINES AT ALL. It appears on
    the plan as its own header with an empty body and a `+`, which is the
    honest rendering of "we owe this and nothing has been picked yet". The
    predecessor manufactured a quantity-only line with a blank bin for this
    case, which then had to be special-cased everywhere downstream — it
    blocked the commit, it counted toward the tally, and it looked identical
    to a real line the clerk had half-filled.

    A DEMAND ALREADY ON THE PLAN IS NOT ADDED TWICE to the demand list, but
    staging it again is still meaningful: it re-runs the auto-pick for
    whatever is still outstanding. Extra shelves are added through the
    location picker (`add_stock_lines`), not by re-staging.
    """
    demand_ids = [d for d in (to_int(v) for v in demand_ids) if d]
    if not demand_ids:
        return (0, 0, 0)

    demands = list(
        PartDemand.objects.filter(
            pk__in=demand_ids,
            domain_id__in=domain_ids,
            deleted_at__isnull=True,
        ).select_related("part")
    )
    lines = load(request)
    staged_demands = load_demands(request)

    staged = paired = 0
    for demand in demands:
        if demand.pk not in staged_demands:
            staged_demands.append(demand.pk)
        staged += 1

        outstanding = outstanding_for(demand, lines)
        if outstanding <= 0:
            continue

        stock = _only_matching_stock(demand.part_id, domain_ids=domain_ids)
        if stock is None:
            continue

        # Capped three ways: a serial is one unit, a bin cannot give more than
        # it holds, and no line ever exceeds what the demand still wants.
        if stock.serial_number:
            quantity = Decimal("1.000")
        else:
            quantity = min(outstanding, stock.quantity_on_hand)
        if quantity <= 0:
            continue

        lines.append(
            new_line(
                demand_id=demand.pk,
                active_inventory_id=stock.pk,
                quantity=quantity,
            )
        )
        paired += 1

    save(request, lines)
    save_demands(request, staged_demands)
    return (staged, paired, len(demand_ids) - staged)


def add_stock_lines(request: HttpRequest, *, demand_id: int, entries, domain_ids=()) -> int:
    """Point a staged demand at one or more inventory locations.

    THE ONLY WAY A LINE IS CREATED by hand. There is no edit-in-place on the
    plan — no changing a line's bin, no retyping its quantity — because a line
    is a single fact ("this many, off this shelf") and half-editing one is how
    the previous version ended up with lines whose quantity no longer matched
    the bin they pointed at. Wrong line: delete it, add it again.

    `entries` is an iterable of `(active_inventory_id, quantity)`; each becomes
    its own line, appended after that demand's existing lines so the plan stays
    grouped. Every quantity is capped at what the bin holds and at what the
    demand still wants, so a shelf big enough to cover the whole demand comes
    in at the DEMAND's number rather than the shelf's.

    A balance holding a different part than the demand asked for is dropped,
    not staged as a mismatch: the picker that feeds this is part-locked, so
    anything else arriving here is a forged POST.
    """
    demand = PartDemand.objects.filter(
        pk=demand_id, domain_id__in=domain_ids, deleted_at__isnull=True
    ).first()
    if demand is None:
        return 0

    lines = load(request)
    remaining = outstanding_for(demand, lines)

    wanted = {}
    for raw_id, raw_qty in entries:
        balance_id = to_int(raw_id)
        if balance_id is not None:
            wanted[balance_id] = to_decimal(raw_qty)

    balances = {
        b.pk: b
        for b in ActiveInventory.objects.filter(
            pk__in=list(wanted),
            part_id=demand.part_id,
            room_id__in=domain_visible_room_ids(domain_ids=domain_ids),
        )
    }
    already = {l.get("active_inventory_id") for l in lines if l.get("active_inventory_id")}

    added = []
    for balance_id, quantity in wanted.items():
        balance = balances.get(balance_id)
        if balance is None or balance_id in already:
            continue

        if balance.serial_number:
            quantity = Decimal("1.000")
        else:
            if quantity is None or quantity <= 0:
                quantity = balance.quantity_on_hand
            quantity = min(quantity, balance.quantity_on_hand)
            # The demand's own ceiling, consumed as each bin takes its share —
            # tick four shelves for a demand of 5 and the fourth comes in at
            # whatever is left of the 5, not at its own full contents.
            if remaining > 0:
                quantity = min(quantity, remaining)
        if quantity <= 0:
            continue

        remaining -= quantity
        added.append(
            new_line(
                demand_id=demand_id,
                active_inventory_id=balance_id,
                quantity=quantity,
            )
        )

    if not added:
        return 0

    # After the demand's last existing line, so its lines read as one block.
    insert_at = len(lines)
    for position in range(len(lines) - 1, -1, -1):
        if lines[position].get("demand_id") == demand_id:
            insert_at = position + 1
            break
    lines[insert_at:insert_at] = added
    save(request, lines)

    demands = load_demands(request)
    if demand_id not in demands:
        demands.append(demand_id)
        save_demands(request, demands)
    return len(added)


# --------------------------------------------------------------------------- #
# Hydration
# --------------------------------------------------------------------------- #


def enrich(lines: list[dict]) -> list[dict]:
    """Turn the stored dicts into something a template can render.

    Bulk-fetches every referenced row in one query per table for the whole
    queue — never one query per line.
    """
    balance_ids = [l["active_inventory_id"] for l in lines if l.get("active_inventory_id")]
    demand_ids = [l["demand_id"] for l in lines if l.get("demand_id")]

    balances = {
        b.pk: b
        for b in ActiveInventory.objects.filter(pk__in=balance_ids).select_related(
            "part", "room", "room__warehouse", "storage_location"
        )
    }
    demands = {
        d.pk: d
        for d in PartDemand.objects.filter(pk__in=demand_ids).select_related(
            "part", "requested_by"
        )
    }

    enriched = []
    for index, line in enumerate(lines):
        balance = balances.get(line.get("active_inventory_id"))
        demand = demands.get(line.get("demand_id"))
        quantity = to_decimal(line.get("quantity")) or Decimal("0")

        if demand is None:
            # The demand was deleted out from under the queue. Surfaced rather
            # than dropped, so the clerk sees why the line will not commit.
            status = "orphaned"
        elif balance is None:
            status = "needs_stock"
        elif balance.part_id != demand.part_id:
            status = "mismatch"
        elif quantity > balance.quantity_on_hand:
            status = "short"
        else:
            status = "ready"

        enriched.append(
            {
                **line,
                "index": index,
                "balance": balance,
                "demand": demand,
                "part": demand.part if demand else (balance.part if balance else None),
                "quantity_decimal": quantity,
                "status": status,
                "is_ready": status == "ready",
                "is_serialised": bool(balance and balance.serial_number),
            }
        )
    return enriched


def group_by_demand(enriched: list[dict], *, demand_ids: list[int] | None = None) -> list[dict]:
    """Roll the plan up per demand — INCLUDING demands with no lines yet.

    `demand_ids` is the staged-demand list, in stage order. A demand in it with
    no lines under it is a group with an empty body and a `+`, which is how
    "we owe this, nothing picked yet" is shown now that no bin-less line is
    fabricated to carry it. Any demand appearing only in the lines (a plan
    saved by an older build) is still grouped, so nothing goes invisible.

    `pct_complete` counts what is ALREADY issued plus what this plan is about
    to hand over, against what was asked for — the clerk's question is "will
    this demand be finished when I hit commit", not "how much of it did
    previous receipts cover".
    """
    ordered_ids = list(demand_ids or [])
    demands_by_id = {}

    for line in enriched:
        demand = line.get("demand")
        if demand is not None:
            demands_by_id[demand.pk] = demand
            if demand.pk not in ordered_ids:
                ordered_ids.append(demand.pk)

    missing = [pk for pk in ordered_ids if pk not in demands_by_id]
    if missing:
        for demand in PartDemand.objects.filter(
            pk__in=missing, deleted_at__isnull=True
        ).select_related("part"):
            demands_by_id[demand.pk] = demand

    groups: dict[int, dict] = {}
    for pk in ordered_ids:
        demand = demands_by_id.get(pk)
        if demand is None:
            continue
        groups[pk] = {
            "demand": demand,
            "part": demand.part,
            "lines": [],
            "requested": demand.quantity_requested,
            "already_issued": demand.issued_qty,
            "staged": Decimal("0"),
        }

    for line in enriched:
        demand = line.get("demand")
        group = groups.get(demand.pk) if demand is not None else None
        if group is None:
            continue
        group["lines"].append(line)
        group["staged"] += line["quantity_decimal"]

    ordered = []
    for pk in ordered_ids:
        group = groups.get(pk)
        if group is None:
            continue
        requested = group["requested"] or Decimal("0")
        covered = group["already_issued"] + group["staged"]
        remaining = requested - covered
        group["covered"] = covered
        group["remaining"] = remaining if remaining > 0 else Decimal("0")
        group["over_by"] = -remaining if remaining < 0 else Decimal("0")
        group["is_over"] = remaining < 0
        group["is_short"] = remaining > 0
        group["is_exact"] = remaining == 0
        group["is_empty"] = not group["lines"]
        # Capped at 100 so an over-issue does not render a bar running off the
        # end of its own track; `is_over` is what colours it red.
        group["pct_complete"] = (
            min(100, int(covered / requested * 100)) if requested > 0 else 0
        )
        group["needs_stock_count"] = sum(
            1 for l in group["lines"] if l["status"] == "needs_stock"
        )
        ordered.append(group)

    return ordered


# --------------------------------------------------------------------------- #
# The receipt header
# --------------------------------------------------------------------------- #

#: The header lives beside the queue rather than in a GET param because it is
#: part of the receipt being built, not a view of it: it must survive F5, the
#: POST-redirect-GET after every stage, and navigating away to look something
#: up. A `?recipient=` param would also make the recipient bookmarkable, which
#: is nonsense for a field that names who is standing at the counter.
HEADER_KEY_PREFIX = "issuance_header_"


def header_key(request: HttpRequest) -> str:
    return f"{HEADER_KEY_PREFIX}{request.user.pk}"


def load_header(request: HttpRequest) -> dict:
    if not request.user.is_authenticated:
        return {}
    return request.session.get(header_key(request), {})


def save_header(request: HttpRequest, header: dict) -> None:
    request.session[header_key(request)] = header
    request.session.modified = True


def clear_header(request: HttpRequest) -> None:
    save_header(request, {})


def recipient(request: HttpRequest):
    """The User this receipt is being made out to, or None.

    NEVER inferred from a staged demand's `requested_by`. A manager routinely
    raises demands against themselves for an activity and a member of staff
    collects the parts, so guessing here would put the wrong name on the
    receipt in the most ordinary case there is.
    """
    from app.administration.models import User

    user_id = to_int(load_header(request).get("issued_to_id"))
    return User.objects.filter(pk=user_id).first() if user_id else None
