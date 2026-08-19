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

    # Whole-procedure expected billable total — the template's "budget" for the
    # task as a whole, the figure a real maintenance event's recorded billable
    # hours (events.MaintenanceDetail.actual_billable_hours) should be judged
    # against. Only TemplateActionSet actually carries this value in practice;
    # the live event has no equivalent field of its own and currently has to be
    # compared by following MaintenanceDetail.template_action_set.labor_hours
    # back to the source template. Not copied onto the event at creation and not
    # enforced against actual_billable_hours anywhere — reference only.
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

    # On a TemplateActionItem/ProtoActionItem, this is the expected duration for
    # one step — the per-step half of the template's labor_hours budget
    # (AbstractActionSet.labor_hours above). ActionFactory copies this value onto
    # the live Action row it creates from the template step, so on Action it's
    # the target the technician's actual Action.billable_hours is implicitly
    # measured against — not automatically compared or enforced, just the number
    # that was expected going in.
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
