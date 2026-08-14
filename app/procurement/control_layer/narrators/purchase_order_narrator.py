"""Narrator: machine-comment text for the PO's Event stream.

D57's audit rule lives here: every mutation to a line or allocation on a
Placed-or-later PO posts a machine comment carrying a JSON snapshot of the row
as it stood IMMEDIATELY BEFORE the change. It is the pre-state that matters —
the post-state is queryable from the row itself.

That is the price of permissiveness. Lines stay editable after placement
because vendors substitute, short-ship, and re-price after an order goes out,
and the record should say what actually happened rather than what was
originally typed. Nothing is silently rewritten and nothing is lost, without
needing a second journal table.
"""

from __future__ import annotations

import json

from django.forms.models import model_to_dict

from app.events.models import Comment
from app.procurement.models import PurchaseOrderStatus

#: Statuses at or beyond which mutations must carry a pre-state snapshot.
#: A Draft PO has not been sent to anyone, so its edits are not yet history.
AUDITED_STATUSES = frozenset(
    {
        PurchaseOrderStatus.PLACED,
        PurchaseOrderStatus.PARTIALLY_RECEIVED,
        PurchaseOrderStatus.RECEIVED,
        PurchaseOrderStatus.CANCELLED,
    }
)


class PurchaseOrderNarrator:
    # ------------------------------------------------------------------ #
    # Comment posting
    # ------------------------------------------------------------------ #

    @classmethod
    def post(cls, *, purchase_order, message: str, actor=None) -> Comment | None:
        """Post a machine comment to the PO's Event. No-op if the PO has no
        Event, which the factory makes impossible in practice."""
        if purchase_order.event_id is None:
            return None
        return Comment.objects.create(
            activity_thread_id=purchase_order.event_id,
            content=message,
            is_human_made=False,
            revision=1,
            created_by=actor,
            updated_by=actor,
        )

    @classmethod
    def post_with_snapshot(
        cls, *, purchase_order, message: str, row, actor=None
    ) -> Comment | None:
        """Post a machine comment carrying the pre-state JSON snapshot.

        Only posts a snapshot when the PO is Placed or later — a Draft order's
        edits are not history yet. The message alone is always posted.
        """
        if purchase_order.status not in AUDITED_STATUSES:
            return cls.post(
                purchase_order=purchase_order, message=message, actor=actor
            )

        snapshot = json.dumps(
            model_to_dict(row), default=str, sort_keys=True, indent=None
        )
        payload = f"{message}\n\nRow before the change:\n{snapshot}"
        return cls.post(purchase_order=purchase_order, message=payload, actor=actor)

    # ------------------------------------------------------------------ #
    # Message text
    # ------------------------------------------------------------------ #

    @staticmethod
    def created(*, po_number: str, vendor_name: str) -> str:
        return f"Purchase order {po_number} created as a draft for {vendor_name}."

    @staticmethod
    def status_changed(*, from_status: str, to_status: str) -> str:
        return f"Status changed from '{from_status}' to '{to_status}'."

    @staticmethod
    def placed(*, po_number: str) -> str:
        return f"{po_number} placed with the vendor."

    @staticmethod
    def submitted_for_approval(*, po_number: str) -> str:
        return f"{po_number} submitted for purchasing approval."

    @staticmethod
    def approved(*, po_number: str, self_approved: bool) -> str:
        text = f"{po_number} approved."
        if self_approved:
            # D71/D76: self-approval is legal, never blocked, but always
            # recorded — the audit trail must say so explicitly.
            return f"{text} Approved by its own creator (self-approval)."
        return text

    @staticmethod
    def denied(*, po_number: str) -> str:
        return f"{po_number} denied."

    @staticmethod
    def received(*, po_number: str) -> str:
        return (
            f"{po_number} closed out as received. This is an explicit decision, not "
            f"a quantity match — outstanding quantity may remain."
        )

    @staticmethod
    def cancelled(*, po_number: str, reason: str) -> str:
        text = f"{po_number} cancelled."
        return f"{text} Reason: {reason}" if reason else text

    @staticmethod
    def line_added(*, line_number: int, part_number: str, quantity) -> str:
        return f"Line {line_number} added: {quantity} x {part_number}."

    @staticmethod
    def line_edited(*, line_number: int) -> str:
        return f"Line {line_number} edited after placement."

    @staticmethod
    def line_cancelled(*, line_number: int, released_demand_count: int) -> str:
        return (
            f"Line {line_number} cancelled. {released_demand_count} demand "
            f"allocation(s) removed; those demands returned to no purchasing "
            f"decision."
        )

    @staticmethod
    def allocation_added(*, demand_id: int, line_number: int, quantity) -> str:
        return f"Demand #{demand_id} allocated {quantity} against line {line_number}."

    @staticmethod
    def allocation_removed(*, demand_id: int, line_number: int) -> str:
        return f"Demand #{demand_id} de-linked from line {line_number}."

    @staticmethod
    def allocations_released(*, count: int) -> str:
        return f"{count} demand allocation(s) released by the cancellation."

    @staticmethod
    def shared_session_formed(*, line_number: int, member_count: int) -> str:
        """The warning the UI must show at the moment of the second allocation
        — a real consequence of an ordinary Buyer action, not something to
        discover later in a report."""
        return (
            f"Line {line_number} now serves {member_count} demands and has become a "
            f"shared demand session. Per-demand arrival quantities are no longer "
            f"reportable for this line."
        )

    @staticmethod
    def package_line_split(
        *, package_number: str, part_number: str, quantity, target_line_number: int
    ) -> str:
        return (
            f"Package {package_number}: {quantity} x {part_number} split onto line "
            f"{target_line_number}."
        )
