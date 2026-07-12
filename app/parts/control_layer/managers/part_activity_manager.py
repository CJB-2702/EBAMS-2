"""PartActivityManager — the single owner of the Part audit feed (§5).

Writes machine (``is_human_made=False``) comments onto the *base Part's*
``documents_thread`` for events that happen to a Part or any of its children (revision added,
status changed, supplier item mapped, alias added). The base Part is resolved
via the reverse activity structs, so "child → base Part" logic lives in one
place and every child event lands on one timeline.

Mirrors ``events.EventHandler._apply_machine_comment`` — same "visible machine
comment" shape — but keeps the parts-specific nullable-thread + bootstrap-domain
concern (§1) out of ``events``. The comment is posted with no ``domain_id`` so
``PartThreadManager`` bootstraps the thread with the variant default domain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.parts.control_layer.managers.part_thread_manager import PartThreadManager

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.events.models import Comment
    from app.parts.models import Part, PartRevision, SupplierItem


class PartActivityManager:
    def __init__(self, part: "Part", actor: "AbstractUser | None" = None) -> None:
        self.part = part
        self.actor = actor

    def record(self, message: str) -> "Comment | None":
        """Post one machine comment onto the base Part thread. No-op on empty."""
        if not message:
            return None
        return PartThreadManager(
            self.part, self.actor, thread_attr="documents_thread"
        ).add_comment(message, is_human_made=False)

    # -- resolvers: build the manager from any child, up to its base Part ---- #

    @classmethod
    def for_part(cls, part: "Part", actor: "AbstractUser | None" = None) -> "PartActivityManager":
        return cls(part, actor)

    @classmethod
    def for_revision(
        cls, revision: "PartRevision", actor: "AbstractUser | None" = None
    ) -> "PartActivityManager":
        from app.parts.control_layer.domain_structs.reverse_structs.revision_activity_struct import (
            RevisionActivityStruct,
        )

        return cls(RevisionActivityStruct.from_instance(revision).part, actor)

    @classmethod
    def for_supplier_item(
        cls, item: "SupplierItem", actor: "AbstractUser | None" = None
    ) -> "PartActivityManager":
        from app.parts.control_layer.domain_structs.reverse_structs.supplier_item_activity_struct import (
            SupplierItemActivityStruct,
        )

        return cls(SupplierItemActivityStruct.from_instance(item).part, actor)
