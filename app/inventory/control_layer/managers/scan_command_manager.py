"""Handler: the reserved `CMDX` command namespace in the scan field
(intake_portal_workflow.md §6).

A barcode scanner is just a keyboard, so the operator's hands never leave the
gun. These five payloads are typed or scanned into the same input as a real
barcode.

| Payload       | Action                                                    |
| :------------ | :-------------------------------------------------------- |
| CMDXDELETE    | Delete the last recorded allocation. Repeatable.          |
| CMDXSERIAL    | Capture a serial onto the last allocation. Forces qty 1.  |
| CMDXQTY1      | Always ADD 1                                              |
| CMDXQTY10     | If quantity is 1, SET to 10; otherwise ADD 10             |
| CMDXQTY100    | If quantity is 1, SET to 100; otherwise ADD 100           |

WHY THE QUANTITY COMMANDS ARE ASYMMETRIC (§6.1). A scan always creates a
quantity of 1. The operator then looks at what is in their hand and says one
of two things: "this is a box of ten" — the 1 was wrong, SET to 10 — or
"here's another box of ten" — the 10 was right, ADD 10. Quantity 1 is
therefore treated as "not yet quantified" rather than as a real count of one,
and the same command reads both intents without a second keystroke. CMDXQTY1
has no such ambiguity to resolve, so it always increments.

THERE ARE NO REDUCE COMMANDS, deliberately. A one-keystroke way to silently
decrement a count is a way to lose stock without a trace, and the recovery
path is not symmetric with the mistake. Over-counting is corrected by editing
the row by hand or walking CMDXDELETE backwards.

A SERIAL NUMBER MEANS QUANTITY 1 (§6.2). All CMDXQTY* commands are REFUSED on
a serialised allocation, and CMDXSERIAL is refused on an allocation already
grown past 1. Both are data-corruption paths, not preferences — a quantity of
5 against one serial is meaningless.

Every command returns loud confirmation text. These are the one place in the
record flow where silence would be dangerous: deleting the wrong row must be
visible immediately (§6.3).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.guards.intake_guard import AllocationValidator
from app.inventory.control_layer.managers.allocation_link_manager import (
    AllocationLinkManager,
)
from app.inventory.models.intake.item_allocation import ItemAllocation

# Exact, whole-payload, case-sensitive. A real barcode that merely CONTAINS
# "CMDX" is never treated as a command (§6.3) — matching on a prefix or a
# substring would make some vendor's part number undeliverable.
COMMAND_DELETE = "CMDXDELETE"
COMMAND_SERIAL = "CMDXSERIAL"
COMMAND_QTY_1 = "CMDXQTY1"
COMMAND_QTY_10 = "CMDXQTY10"
COMMAND_QTY_100 = "CMDXQTY100"

QUANTITY_COMMANDS = {
    COMMAND_QTY_1: Decimal("1"),
    COMMAND_QTY_10: Decimal("10"),
    COMMAND_QTY_100: Decimal("100"),
}

ALL_COMMANDS = frozenset(
    {COMMAND_DELETE, COMMAND_SERIAL, *QUANTITY_COMMANDS}
)


class ScanCommandHandler:
    @staticmethod
    def is_command(payload: str) -> bool:
        """Whole-payload equality only. Never `startswith`, never `in`."""
        return payload in ALL_COMMANDS

    @staticmethod
    def requires_serial_prompt(payload: str) -> bool:
        """CMDXSERIAL needs a value the scan field cannot supply, so the
        presentation layer opens a single-field capture for it — exactly what
        the modals guide permits a modal to be (§6.3)."""
        return payload == COMMAND_SERIAL

    # ------------------------------------------------------------------ #

    @classmethod
    def _last_allocation(cls, *, session) -> ItemAllocation:
        allocation = (
            session.allocations.filter(deleted_at__isnull=True)
            .select_related("part")
            .order_by("-id")
            .first()
        )
        if allocation is None:
            raise InventoryValidationError(
                ["There is nothing recorded on this session yet."]
            )
        return allocation

    @classmethod
    def execute(cls, *, session, payload: str, serial_number: str = "", actor=None) -> str:
        """Run one command and return its confirmation text. Raises
        `InventoryValidationError` for anything refused — unlike association,
        a refused command MUST be shown, because the operator asked for it."""
        if payload == COMMAND_DELETE:
            return cls.delete_last(session=session, actor=actor)
        if payload == COMMAND_SERIAL:
            return cls.apply_serial(
                session=session, serial_number=serial_number, actor=actor
            )
        if payload in QUANTITY_COMMANDS:
            return cls.apply_quantity(session=session, payload=payload, actor=actor)
        raise InventoryValidationError([f"'{payload}' is not a scan command."])

    # ------------------------------------------------------------------ #

    @classmethod
    def delete_last(cls, *, session, actor=None) -> str:
        """Walks backwards continuously, one row per invocation (Q17)."""
        allocation = cls._last_allocation(session=session)
        label = f"{allocation.quantity} x {allocation.part.part_number}"
        allocation.deleted_at = timezone.now()
        allocation.updated_by = actor
        allocation.save(update_fields=["deleted_at", "updated_by", "updated_at"])
        return f"Deleted last entry: {label}."

    @classmethod
    def apply_serial(cls, *, session, serial_number: str, actor=None) -> str:
        serial_number = (serial_number or "").strip()
        if not serial_number:
            raise InventoryValidationError(["No serial number was entered."])

        allocation = cls._last_allocation(session=session)
        if allocation.quantity != 1:
            # Refused rather than silently resolved: the operator has already
            # asserted this row is a batch, and a serial says it is one
            # object. Only they can say which is true.
            raise InventoryValidationError(
                [
                    f"That entry is {allocation.quantity} x "
                    f"{allocation.part.part_number}. A serial number identifies "
                    f"one object — split or re-enter it before adding a serial."
                ]
            )
        AllocationValidator.check_composite_sn_unique(
            part_id=allocation.part_id,
            serial_number=serial_number,
            exclude_allocation_id=allocation.pk,
        )
        allocation.serial_number = serial_number
        allocation.composite_sn = f"{allocation.part_id}:{serial_number}"
        allocation.updated_by = actor
        allocation.save(
            update_fields=["serial_number", "composite_sn", "updated_by", "updated_at"]
        )
        return f"Serial {serial_number} recorded on {allocation.part.part_number}."

    @classmethod
    def apply_quantity(cls, *, session, payload: str, actor=None) -> str:
        step = QUANTITY_COMMANDS[payload]
        allocation = cls._last_allocation(session=session)

        if allocation.serial_number:
            raise InventoryValidationError(
                [
                    f"{allocation.part.part_number} carries serial "
                    f"{allocation.serial_number} — a serialised entry is always "
                    f"one unit and its quantity cannot be changed."
                ]
            )

        # Set-if-1, else add — except CMDXQTY1, which has nothing to disambiguate.
        if step == Decimal("1") or allocation.quantity != Decimal("1"):
            new_quantity = allocation.quantity + step
            verb = "Added"
        else:
            new_quantity = step
            verb = "Set"

        with transaction.atomic():
            # Growing a LINKED row is a link write in disguise, so it goes
            # through the same cap the original link went through (§7.2).
            AllocationLinkManager.set_quantity(
                allocation=allocation, quantity=new_quantity, actor=actor
            )
        return (
            f"{verb} {step} — {allocation.part.part_number} is now "
            f"{new_quantity}."
        )
