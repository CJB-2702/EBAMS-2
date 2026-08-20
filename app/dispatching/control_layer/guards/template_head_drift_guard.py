"""Guard type: Policy. Refuses a commit when the lineage's head moved while
the draft was open — without this, the second of two concurrent committers
silently discards the first's work (dispatching_starter_kit/
1_dispatch_templates.md §3.3, R6)."""

from __future__ import annotations


class TemplateHeadDriftPolicy:
    @classmethod
    def check(cls, *, template, draft_prior_revision_id: int | None) -> None:
        current_head_id = template.head_revision_id
        if draft_prior_revision_id != current_head_id:
            raise ValueError(
                "This template was revised while you were editing — review "
                f"revision #{current_head_id} and reapply your changes."
            )
