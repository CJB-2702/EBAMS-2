"""Handler: the Basic Package Manager's entire submit path.

This is a Handler and not a view function stitching manager calls together, on
purpose. The submission is a single decision about a whole PO's shipment plan —
several packages, several line movements, possibly a package created and
another one re-laid-out in the same click — and it either lands or it does not.

--------------------------------------------------------------------------
ALL OR NOTHING, EXPLICITLY.
--------------------------------------------------------------------------

Any validation or transaction failure rejects the ENTIRE submission. Nothing is
written, not even the parts that were individually fine. The session draft
survives untouched and the page re-renders with errors keyed to the package or
line that tripped them.

A partial commit is the failure mode worth spending code to avoid: the Buyer
made five decisions in one sitting, and "three of them landed" leaves them
unsure which, with no way to tell apart a decision they made from one the system
dropped. Re-doing all five is cheap; auditing which of five landed is not.

--------------------------------------------------------------------------
CLIENT STATE IS AN INPUT, NEVER A FACT.
--------------------------------------------------------------------------

The payload says what the Buyer WANTS. Everything about what currently exists —
which packages are on this order, which are locked, what their lines are — is
re-derived from the database here, ignoring whatever the page echoed back. A
package that was delivered while the tab sat open is locked at submit even
though the draft was seeded before it moved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.factories.package_factory import PackageFactory
from app.procurement.control_layer.managers.package_line_manager import (
    PackageLineManager,
)
from app.procurement.control_layer.managers.package_status_manager import (
    PackageStatusManager,
)
from app.procurement.control_layer.narrators.package_narrator import PackageNarrator
from app.procurement.models import Package, PackageLine, PurchaseOrderLine
from django.utils import timezone


@dataclass
class SubmitSummary:
    """What actually happened, for the success flash on PO detail."""

    packages_created: int = 0
    packages_modified: int = 0
    lines_moved: int = 0
    created_numbers: list[str] = field(default_factory=list)

    def as_message(self) -> str:
        if not (self.packages_created or self.packages_modified or self.lines_moved):
            return "No changes to apply — the plan already matches what is on file."
        bits = []
        if self.packages_created:
            bits.append(f"{self.packages_created} package(s) created")
        if self.packages_modified:
            bits.append(f"{self.packages_modified} package(s) updated")
        if self.lines_moved:
            bits.append(f"{self.lines_moved} line assignment(s) changed")
        return "Shipment plan saved — " + ", ".join(bits) + "."


class BasicPackageManagerSubmitHandler:
    """Takes the whole draft, validates everything, then commits once."""

    def __init__(self, *, purchase_order, draft: dict, actor=None) -> None:
        self.purchase_order = purchase_order
        self.draft = draft
        self.actor = actor
        self.errors: list[str] = []
        #: temp_id -> [error, ...]. The template keys its inline messages off
        #: this so a failure lands on the card that caused it, not in a banner
        #: at the top of a twelve-package page.
        self.card_errors: dict[str, list[str]] = {}

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #

    def run(self) -> SubmitSummary:
        """Validate everything, then write everything. Raises
        ProcurementValidationError with nothing written if any check fails."""
        plan = self._validate()
        if self.errors or self.card_errors:
            raise ProcurementValidationError(self._flat_errors())
        return self._commit(plan)

    def _flat_errors(self) -> list[str]:
        flat = list(self.errors)
        for card_messages in self.card_errors.values():
            flat.extend(card_messages)
        return flat or ["The shipment plan could not be saved."]

    def _fail(self, temp_id: str | None, message: str) -> None:
        if temp_id is None:
            self.errors.append(message)
        else:
            self.card_errors.setdefault(temp_id, []).append(message)

    # ------------------------------------------------------------------ #
    # Validation — re-derives every fact from the database
    # ------------------------------------------------------------------ #

    def _validate(self) -> list[dict]:
        """Build the write plan. Returns one entry per card that needs work."""
        po_lines = {
            line.pk: line
            for line in PurchaseOrderLine.objects.filter(
                purchase_order=self.purchase_order, deleted_at__isnull=True
            ).select_related("part")
        }
        existing = {
            package.pk: package
            for package in Package.objects.filter(
                purchase_order=self.purchase_order, deleted_at__isnull=True
            )
        }

        plan: list[dict] = []
        for card in self.draft.get("packages", []):
            temp_id = card["temp_id"]
            package_id = card.get("package_id")

            desired = self._desired_lines(card, po_lines)
            if desired is None:
                continue  # errors already recorded

            if package_id is None:
                if not desired:
                    # A card with no chips is a plan in progress, not an error.
                    # Silently skipped rather than refused — refusing would
                    # block the whole submission over an empty box the Buyer
                    # simply has not filled yet.
                    continue
                plan.append({"card": card, "mode": "create", "desired": desired})
                continue

            package = existing.get(package_id)
            if package is None:
                self._fail(
                    temp_id,
                    "This package is no longer on this order — it was deleted or "
                    "moved while the planner was open. Reload the page.",
                )
                continue

            # THE LOCK RULE, RE-CHECKED SERVER SIDE. The template also hides
            # the controls, but the template is not a security boundary and the
            # package may have moved since the draft was seeded.
            from app.procurement.presentation_layer.tools import (
                basic_package_session as session_tool,
            )

            if session_tool.is_locked(package):
                if self._locked_card_changed(package, desired):
                    self._fail(
                        temp_id,
                        f"Package {package.package_number} is locked "
                        f"({session_tool.lock_reason(package)}) and cannot be "
                        f"changed here. Nothing was saved.",
                    )
                continue

            current = self._current_lines(package)
            if current is None:
                self._fail(
                    temp_id,
                    f"Package {package.package_number} has two lines pointing at "
                    f"the same order line, which the planner cannot represent as "
                    f"one chip. Resolve it on the package's own edit page.",
                )
                continue

            if current != desired or self._header_changed(package, card):
                plan.append(
                    {
                        "card": card,
                        "mode": "update",
                        "package": package,
                        "current": current,
                        "desired": desired,
                    }
                )

        return plan

    def _desired_lines(self, card: dict, po_lines: dict) -> dict[int, Decimal] | None:
        """The card's chips as {po_line_id: quantity}, validated."""
        from app.procurement.presentation_layer.tools import (
            basic_package_session as session_tool,
        )

        temp_id = card["temp_id"]
        desired: dict[int, Decimal] = {}
        ok = True
        for chip in card.get("lines", []):
            po_line_id = chip.get("po_line_id")
            quantity = session_tool.to_decimal(chip.get("quantity"))

            if po_line_id not in po_lines:
                self._fail(
                    temp_id,
                    f"Order line {po_line_id} is not on this purchase order any "
                    f"more. Remove it from the plan and try again.",
                )
                ok = False
                continue
            if quantity is None or quantity <= 0:
                self._fail(
                    temp_id,
                    f"{po_lines[po_line_id].part.part_number} has a quantity of "
                    f"'{chip.get('quantity')}', which is not a positive number.",
                )
                ok = False
                continue
            desired[po_line_id] = quantity
        return desired if ok else None

    @staticmethod
    def _current_lines(package: Package) -> dict[int, Decimal] | None:
        """What is on file, as {po_line_id: quantity}.

        Lines with a NULL purchase_order_line, or pointing at another order's
        line, are deliberately excluded and therefore never touched: they have
        no chip in this tool, so the diff must not read their absence from the
        draft as "delete this".

        Returns None when two active lines share one PO line — the planner's
        one-chip-per-line model cannot represent that, and guessing which to
        adjust would silently destroy a split.
        """
        current: dict[int, Decimal] = {}
        for line in package.lines.filter(
            deleted_at__isnull=True, purchase_order_line__isnull=False
        ):
            if line.purchase_order_line_id in current:
                return None
            current[line.purchase_order_line_id] = line.quantity
        return current

    @staticmethod
    def _locked_card_changed(package: Package, desired: dict[int, Decimal]) -> bool:
        """A locked card is allowed to come back unchanged — the page posts
        every card, including the read-only ones — but any actual edit is
        refused.

        SUMMED per PO line, not one entry per row, because a split package
        legitimately carries several rows against one line and the session
        seeds it as a single aggregated chip. Comparing row-by-row against an
        aggregated draft would flag every split package as "changed" and
        reject submissions that touched nothing.
        """
        current: dict[int, Decimal] = {}
        for line in package.lines.filter(
            deleted_at__isnull=True, purchase_order_line__isnull=False
        ):
            current[line.purchase_order_line_id] = (
                current.get(line.purchase_order_line_id, Decimal("0")) + line.quantity
            )
        return current != desired

    @staticmethod
    def _header_changed(package: Package, card: dict) -> bool:
        return (
            (card.get("shipment_id") or "") != (package.shipment_id or "")
            or (card.get("carrier") or "") != (package.carrier or "")
            or (card.get("notes") or "") != (package.notes or "")
            or (card.get("shipped_date") or "")
            != (package.shipped_date.isoformat() if package.shipped_date else "")
            or (card.get("expected_arrival_date") or "")
            != (
                package.expected_arrival_date.isoformat()
                if package.expected_arrival_date
                else ""
            )
        )

    # ------------------------------------------------------------------ #
    # Commit — one transaction for the whole plan
    # ------------------------------------------------------------------ #

    def _commit(self, plan: list[dict]) -> SubmitSummary:
        summary = SubmitSummary()
        if not plan:
            return summary

        with transaction.atomic():
            for entry in plan:
                if entry["mode"] == "create":
                    self._create_package(entry, summary)
                else:
                    self._update_package(entry, summary)
        return summary

    def _create_package(self, entry: dict, summary: SubmitSummary) -> None:
        card = entry["card"]
        # Created with NO lines, then each chip added with its PO line named
        # explicitly. The factory's copy-on-create resolves a line by part,
        # which is the right default for a receiver typing a packing slip and
        # the wrong one here — the Buyer has already said which line each chip
        # came from, and a part appearing on two lines must not be re-guessed.
        package = PackageFactory.create(
            purchase_order=self.purchase_order,
            domain=self.purchase_order.domain,
            lines=None,
            actor=self.actor,
            shipment_id=card.get("shipment_id", ""),
            carrier=card.get("carrier", ""),
            shipped_date=card.get("shipped_date") or None,
            expected_arrival_date=card.get("expected_arrival_date") or None,
            notes=card.get("notes", ""),
        )
        for po_line_id, quantity in entry["desired"].items():
            po_line = PurchaseOrderLine.objects.get(pk=po_line_id)
            PackageLineManager.add_line(
                package=package,
                part_id=po_line.part_id,
                quantity=quantity,
                actor=self.actor,
                purchase_order_line=po_line,
                commit=False,
            )
            summary.lines_moved += 1

        PackageStatusManager.refresh_mixed_po_assignments(
            package=package, actor=self.actor, commit=True
        )
        summary.packages_created += 1
        summary.created_numbers.append(package.package_number)

    def _update_package(self, entry: dict, summary: SubmitSummary) -> None:
        package = entry["package"]
        current: dict[int, Decimal] = entry["current"]
        desired: dict[int, Decimal] = entry["desired"]
        card = entry["card"]

        self._save_header(package, card)

        for po_line_id, quantity in desired.items():
            if po_line_id not in current:
                po_line = PurchaseOrderLine.objects.get(pk=po_line_id)
                PackageLineManager.add_line(
                    package=package,
                    part_id=po_line.part_id,
                    quantity=quantity,
                    actor=self.actor,
                    purchase_order_line=po_line,
                    commit=False,
                )
                summary.lines_moved += 1
            elif current[po_line_id] != quantity:
                line = package.lines.get(
                    purchase_order_line_id=po_line_id, deleted_at__isnull=True
                )
                line.quantity = quantity
                line.updated_by = self.actor
                line.save(update_fields=["quantity", "updated_by", "updated_at"])
                summary.lines_moved += 1

        removed = set(current) - set(desired)
        if removed:
            now = timezone.now()
            # Soft delete: a chip dragged out of a box is a plan correction,
            # and the row it came from is part of that plan's history.
            PackageLine.objects.filter(
                package=package,
                purchase_order_line_id__in=removed,
                deleted_at__isnull=True,
            ).update(deleted_at=now, updated_by=self.actor, updated_at=now)
            summary.lines_moved += len(removed)

        PackageStatusManager.refresh_mixed_po_assignments(
            package=package, actor=self.actor, commit=True
        )
        PackageNarrator.post(
            package=package,
            message=(
                f"Shipment plan updated in the package manager: "
                f"{len(desired)} line(s) now assigned to this package."
            ),
            actor=self.actor,
        )
        summary.packages_modified += 1

    def _save_header(self, package: Package, card: dict) -> None:
        if not self._header_changed(package, card):
            return
        package.shipment_id = card.get("shipment_id", "")
        package.carrier = card.get("carrier", "")
        package.notes = card.get("notes", "")
        package.shipped_date = card.get("shipped_date") or None
        package.expected_arrival_date = card.get("expected_arrival_date") or None
        package.updated_by = self.actor
        package.save(
            update_fields=[
                "shipment_id",
                "carrier",
                "notes",
                "shipped_date",
                "expected_arrival_date",
                "updated_by",
                "updated_at",
            ]
        )
