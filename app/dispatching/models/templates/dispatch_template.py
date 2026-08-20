from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class DispatchTemplate(AuditFieldsMixin):
    """The lineage — a standing identity. Carries only what is not versioned:
    which domain owns it, whether it is retired, and which revision is
    current. Everything else (title, pre-fill values, the requirement
    manifest) belongs to a DispatchTemplateRevision, never to this row — that
    is what keeps a revision immutable (D3, dispatching_starter_kit/
    1_dispatch_templates.md §2).

    No SoftDeleteMixin: a lineage is deleted only in the one legitimate case
    where none of its revisions was ever named by a dispatch (§5) — that is
    hard deletion, not the usual soft-delete path, and is a control-layer
    decision, not a schema one.
    """

    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="dispatch_templates",
    )
    head_revision = models.ForeignKey(
        "dispatching.DispatchTemplateRevision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="head_of_template",
        help_text="The revision currently offered to requesters. Nullable only "
                   "in the moment between creating the lineage and committing "
                   "its first revision.",
    )
    copied_from_revision = models.ForeignKey(
        "dispatching.DispatchTemplateRevision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="templates_copied_from",
        help_text="Provenance, not dependency — improving the source never "
                   "touches this lineage.",
    )

    is_retired = models.BooleanField(default=False)
    retired_reason = models.TextField(blank=True)
    retired_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatch_templates_retired",
    )
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "dispatch_template"
        permissions = [
            ("template_author", "Can open and edit a working draft, discard it, copy a template into a new lineage"),
            ("template_commit", "Can commit a working draft as a new revision; retire and reinstate a lineage"),
        ]

    def __str__(self) -> str:
        title = self.head_revision.title if self.head_revision_id else f"Template #{self.pk}"
        return title
