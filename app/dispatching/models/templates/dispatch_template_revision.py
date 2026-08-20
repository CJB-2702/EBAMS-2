from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.events.models.details.dispatching import DispatchScope


class DispatchTemplateRevision(AuditFieldsMixin):
    """One version of a template. Immutable from the moment it exists — no
    exceptions, no admin override (R1, dispatching_starter_kit/
    1_dispatch_templates.md §3.1). Immutability is enforced in the control
    layer (a guard refuses updates after creation); the schema itself does
    not, and cannot, prevent an ORM-level update — see model_patterns.md §7.

    A revision is created exactly once, at commit — there are no draft rows
    (D4). Creation IS commit, so who/when it was committed is exactly
    created_by/created_at from AuditFieldsMixin; no separate committed_by/
    committed_at pair is kept.

    The requirement manifest (the five mirrored requirement tables plus
    material requirements) hangs off this row, never off the lineage — see
    dispatching.models.templates.template_requested_* and
    dispatching.models.templates.template_material_requirement.
    """

    template = models.ForeignKey(
        "dispatching.DispatchTemplate",
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)

    # ── Pre-fill values — every field optional; a manifest-only template is
    # legitimate, not a degenerate case (§6.2) ────────────────────────────────
    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatch_template_revisions",
    )
    asset_subclass_text = models.CharField(max_length=255, blank=True)
    dispatch_scope = models.CharField(max_length=20, choices=DispatchScope.choices, blank=True)
    activity_location = models.CharField(max_length=255, blank=True)
    estimated_meter_usage = models.FloatField(null=True, blank=True)
    headcount = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    change_note = models.TextField(
        blank=True,
        help_text="What changed and why — required by the control layer at commit.",
    )
    prior_revision = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subsequent_revisions",
    )

    class Meta:
        db_table = "dispatch_template_revision"
        ordering = ["template", "revision_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "revision_number"],
                name="uq_dispatch_template_revision_number",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} (rev {self.revision_number})"
