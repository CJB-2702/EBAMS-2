from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class PlanStatus(models.TextChoices):
    ACTIVE = "Active", "Active"
    INACTIVE = "Inactive", "Inactive"


class PlanFrequencyType(models.TextChoices):
    CALENDAR = "Calendar", "Calendar"
    METER = "Meter", "Meter"


class MaintenancePlan(AuditFieldsMixin, SoftDeleteMixin):
    """
    Recurring maintenance schedule rule (calendar or meter based).
    Instantiates Maintenance Events from a TemplateActionSet on a schedule.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=PlanStatus.choices,
        default=PlanStatus.ACTIVE,
    )

    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.PROTECT,
        related_name="maintenance_plans",
    )
    asset_models = models.ManyToManyField(
        "assets.AssetModel",
        blank=True,
        related_name="maintenance_plans",
    )
    template_action_set = models.ForeignKey(
        "maintenance.TemplateActionSet",
        on_delete=models.PROTECT,
        related_name="maintenance_plans",
    )

    # Frequency
    frequency_type = models.CharField(
        max_length=20,
        choices=PlanFrequencyType.choices,
    )
    delta_days = models.FloatField(null=True, blank=True)
    delta_m1 = models.FloatField(null=True, blank=True)
    delta_m2 = models.FloatField(null=True, blank=True)
    delta_m3 = models.FloatField(null=True, blank=True)
    delta_m4 = models.FloatField(null=True, blank=True)

    # Domain scoping
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="maintenance_plans",
    )

    activity_thread = models.OneToOneField(
        "events.ActivityThread",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="maintenance_plan_thread",
    )

    class Meta:
        db_table = "maintenance_plan"

    def __str__(self) -> str:
        return f"{self.name} ({self.frequency_type})"

    def save(self, *args, **kwargs):
        if not self.activity_thread_id and self.domain_id:
            from app.events.models import ActivityThread
            thread = ActivityThread.objects.create(
                domain_id=self.domain_id,
                created_by=getattr(self, "created_by", None),
                updated_by=getattr(self, "updated_by", None),
            )
            self.activity_thread = thread
        super().save(*args, **kwargs)

