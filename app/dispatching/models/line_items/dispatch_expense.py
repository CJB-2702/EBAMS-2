from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.dispatching.models.enums import ExpenseStatus, ExpenseType


class DispatchExpense(AuditFieldsMixin):
    """Contract and reimbursement, one record distinguished by type — money
    went to somebody, against a reference, because we could not do this
    ourselves. No currency field: one organisational currency (§3.3).

    Carries its own activity thread for invoices, claim forms, and the
    narrative of what happened — history lives in comments, not a structured
    change log, unlike ReservationUpdate. See
    dispatching_starter_kit/4_dispatch_line_items.md §3.
    """

    dispatch = models.ForeignKey(
        "events.DispatchingDetail",
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    expense_type = models.CharField(max_length=20, choices=ExpenseType.choices)
    status = models.CharField(
        max_length=20,
        choices=ExpenseStatus.choices,
        default=ExpenseStatus.PLANNED,
    )

    counterparty_vendor = models.ForeignKey(
        "procurement.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatch_expenses",
    )
    counterparty_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Used when the counterparty is not a registered vendor.",
    )
    payee = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatch_expenses_as_payee",
        help_text="For a reimbursement, the person being paid back.",
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    external_reference = models.CharField(max_length=200, blank=True)
    reason = models.TextField(
        blank=False,
        help_text="Required — why this was needed instead of our own assets.",
    )
    notes = models.TextField(blank=True)
    account_codes = models.CharField(max_length=255, blank=True)

    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatch_expenses_cancelled",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)

    activity_thread = models.OneToOneField(
        "events.ActivityThread",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="dispatch_expense_thread",
    )

    class Meta:
        db_table = "dispatch_expense"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="dispatch_expense_amount_non_negative",
            ),
        ]
        permissions = [
            ("expense_record", "Can add, edit, commit, complete, and cancel expenses"),
        ]

    def __str__(self) -> str:
        return f"{self.get_expense_type_display()} — Dispatch #{self.dispatch_id} — {self.amount}"
