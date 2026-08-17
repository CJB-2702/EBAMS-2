from django.db import models

from app.events.models.event import Event, EventType


class MaintenanceDetail(Event):
    """
    Detail table for event_type='maintenance'.

    Covers scheduled maintenance, reactive repairs, inspections, etc.
    """

    maintenance_type = models.CharField(
        max_length=50,
        choices=[
            ("scheduled", "Scheduled"),
            ("reactive", "Reactive"),
            ("inspection", "Inspection"),
            ("preventive", "Preventive"),
        ],
        blank=True,
    )
    work_order_reference = models.CharField(max_length=100, blank=True)
    maintenance_schedule = models.CharField(max_length=255, blank=True)

    # Relationships
    template_action_set = models.ForeignKey(
        "maintenance.TemplateActionSet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_details",
    )
    maintenance_plan = models.ForeignKey(
        "maintenance.MaintenancePlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_details",
    )
    
    actual_billable_hours = models.FloatField(null=True, blank=True)
    
    # Assignments
    assigned_user = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_maintenance_events",
    )
    assigned_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_maintenance_events_by_me",
    )
    completed_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_maintenance_events",
    )
    
    # Notes
    completion_notes = models.TextField(blank=True)
    blocker_notes = models.TextField(blank=True)
    
    # Readings & Assets
    meter_reading = models.ForeignKey(
        "assets.MeterHistory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_events",
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="maintenance_details",
    )

    class Meta:
        db_table = "event_detail_maintenance"

    def save(self, *args, **kwargs) -> None:
        self.event_type = EventType.MAINTENANCE
        super().save(*args, **kwargs)
