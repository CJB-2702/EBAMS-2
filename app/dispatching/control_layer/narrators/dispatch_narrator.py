"""Narrator: the headline feature (build_phase_2_control_layer.md Step 4) —
plain-language sentences for the dispatch's own timeline. Every line item
change posts one of these onto DispatchingDetail's Event thread, in the
same transaction as the change (doc 4 §5)."""

from __future__ import annotations


def _who(actor) -> str:
    return getattr(actor, "username", None) or "system"


class DispatchNarrator:
    # ── Line items generally ──────────────────────────────────────────────
    @staticmethod
    def reservation_attached(*, reservation_id: int, asset_name: str) -> str:
        return f"Reservation #{reservation_id} attached ({asset_name})."

    @staticmethod
    def reservation_milestone(*, reservation_id: int, milestone: str) -> str:
        return f"Reservation #{reservation_id}: {milestone}"

    @staticmethod
    def expense_added(*, expense_type: str, counterparty: str, amount) -> str:
        return f"{expense_type.title()} expense added — {counterparty}, {amount}."

    @staticmethod
    def expense_status_changed(*, expense_id: int, previous: str, new: str) -> str:
        return f"Expense #{expense_id} {previous} -> {new}."

    @staticmethod
    def expense_cancelled(*, expense_id: int, reason: str) -> str:
        return f"Expense #{expense_id} cancelled — \"{reason}\"."

    # ── Lifecycle ────────────────────────────────────────────────────────
    @staticmethod
    def submitted(*, actor) -> str:
        return f"Submitted by {_who(actor)}."

    @staticmethod
    def taken_under_review(*, actor) -> str:
        return f"Taken under review by {_who(actor)}."

    @staticmethod
    def fixes_requested(*, actor, reason: str) -> str:
        return f"Sent back for fixes by {_who(actor)} — \"{reason}\"."

    @staticmethod
    def resubmitted(*, actor) -> str:
        return f"Resubmitted by {_who(actor)}."

    @staticmethod
    def rejected(*, actor, reason: str, category: str) -> str:
        return f"Rejected by {_who(actor)} ({category}) — \"{reason}\"."

    @staticmethod
    def completed(*, actor) -> str:
        return f"Marked completed by {_who(actor)}."

    @staticmethod
    def cancelled(*, actor, reason: str) -> str:
        return f"Cancelled by {_who(actor)} — \"{reason}\"."

    @staticmethod
    def superseded_by(*, new_dispatch_id: int) -> str:
        return f"Superseded by Dispatch #{new_dispatch_id}."

    @staticmethod
    def demand_raised(*, part_number: str, quantity) -> str:
        return f"Material demand raised: {quantity} x {part_number}."

    @staticmethod
    def requirement_added(*, requirement_kind: str, label: str, is_required: bool) -> str:
        flag = "required" if is_required else "preferred"
        return f"Added {requirement_kind} requirement ({flag}): {label}."

    @staticmethod
    def requirement_removed(*, requirement_kind: str, label: str) -> str:
        return f"Removed {requirement_kind} requirement: {label}."

    @staticmethod
    def crew_added(*, username: str, role: str) -> str:
        return f"{username} added to crew as {role}."

    @staticmethod
    def crew_removed(*, username: str) -> str:
        return f"{username} removed from crew."
