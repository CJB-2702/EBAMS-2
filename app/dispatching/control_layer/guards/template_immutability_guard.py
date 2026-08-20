"""Guard type: Policy. A committed DispatchTemplateRevision is never
writable, ever — no admin override, no exceptions (R1,
dispatching_starter_kit/1_dispatch_templates.md §3.1).

No control-layer method in this app offers an "edit revision" verb; this
guard exists as the explicit, greppable statement of that invariant and a
defensive stop for any future code tempted to add one. The five requirement
mirror tables and the material-requirement table point at a revision, and
none of their managers expose an update path either — see
RequirementManifestEditor (dispatch-side only) and
TemplateRevisionCommitManager (create-once)."""

from __future__ import annotations


class TemplateImmutabilityPolicy:
    @classmethod
    def refuse(cls, *, revision_id: int) -> None:
        raise ValueError(
            f"Revision #{revision_id} is immutable and cannot be edited. "
            "Publish a new revision instead."
        )
