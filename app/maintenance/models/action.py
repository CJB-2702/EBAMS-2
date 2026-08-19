from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.maintenance.models.abstract_mixins import AbstractActionItem


class ActionStatus(models.TextChoices):
    NOT_STARTED = "Not Started", "Not Started"
    IN_PROGRESS = "In Progress", "In Progress"
    COMPLETE = "Complete", "Complete"
    SKIPPED = "Skipped", "Skipped"
    FAILED = "Failed", "Failed"
    BLOCKED = "Blocked", "Blocked"


class Action(AbstractActionItem, AuditFieldsMixin, SoftDeleteMixin):
    """
    Individual action step execution record within a Maintenance Event.
    """
    event_detail = models.ForeignKey(
        "events.MaintenanceDetail",
        on_delete=models.CASCADE,
        related_name="actions",
    )
    template_action_item = models.ForeignKey(
        "maintenance.TemplateActionItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )
    
    sequence_order = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=ActionStatus.choices,
        default=ActionStatus.NOT_STARTED,
    )
    
    scheduled_start_time = models.DateTimeField(null=True, blank=True)

    # start_time / end_time: set once each by ActionContext.start() / .complete()
    # (actual wall-clock — when work genuinely began and ended). Reference only:
    # nothing enforces start_time < end_time, and nothing computes a duration from
    # them automatically. They exist to answer "how long did this actually take"
    # as a fact independent of billable_hours below, which answers a different
    # question ("how much of that gets billed"). The two are expected to diverge
    # — e.g. 6 hours elapsed (end_time - start_time) but only 4 billable_hours
    # recorded — and that divergence is not an error to correct, just something
    # to surface if it ever needs comparing.
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)

    # The technician-recorded actual billable figure for this step, entered
    # independently of start_time/end_time above (never derived from them).
    # Its expectation baseline is TemplateActionItem.estimated_duration_minutes
    # on the template step this action was created from (see
    # ActionFactory / template_action_item field, and AbstractActionSet.labor_hours
    # for the whole-procedure figure) — the template says what a task should take;
    # this field is what one technician says it actually took to bill for.
    billable_hours = models.FloatField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)
    
    # Assignment
    assigned_user = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_actions",
    )
    assigned_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_actions_by_me",
    )
    completed_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_actions",
    )

    class Meta:
        db_table = "maintenance_action"
        ordering = ["sequence_order"]

    def __str__(self) -> str:
        return f"{self.action_name} — {self.status} (Seq: {self.sequence_order})"
