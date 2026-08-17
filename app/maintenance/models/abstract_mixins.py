from django.db import models


class AbstractActionSet(models.Model):
    """
    Abstract base class for maintenance action sets (live and template).
    Contains fields defining the high-level task/procedure.
    """
    task_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    estimated_duration = models.FloatField(null=True, blank=True, help_text="Estimated duration in hours")
    safety_review_required = models.BooleanField(default=False)
    staff_count = models.IntegerField(null=True, blank=True)
    parts_cost = models.FloatField(null=True, blank=True)
    labor_hours = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True


class AbstractActionItem(models.Model):
    """
    Abstract base class for individual action items/steps.
    """
    action_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    estimated_duration_minutes = models.IntegerField(null=True, blank=True)
    safety_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        abstract = True


class AbstractActionTool(models.Model):
    """
    Abstract base class for tool/equipment requirements.
    """
    tool = models.ForeignKey(
        "parts.Tool",
        on_delete=models.SET_NULL,
        related_name="%(class)s_usages",
        null=True,
        blank=True,
        help_text="Optional catalog tool reference",
    )
    tool_name = models.CharField(max_length=200, blank=True, help_text="Display or ad-hoc tool name")
    quantity_required = models.PositiveIntegerField(default=1)
    specifications = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        abstract = True


class AbstractPartDemandRequirement(models.Model):
    """
    Abstract base class for part requirements.
    """
    quantity_required = models.DecimalField(max_digits=12, decimal_places=3, default=1.000)
    notes = models.TextField(blank=True)

    class Meta:
        abstract = True
