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
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
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
