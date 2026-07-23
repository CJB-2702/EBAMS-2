"""PartActivityNarrator — the single owner of the Part audit feed (§5).

Posts machine (``is_human_made=False``) comments onto the *base Part's*
``documents_thread`` for events that happen to a Part or any of its children
(revision added, status changed, supplier item mapped, alias added). The base
Part is resolved via the reverse activity structs, so "child → base Part"
logic lives in one place and every child event lands on one timeline. All
comment writes delegate to ``events.ActivityThreadManager`` — never
reimplemented here.

# DELIBERATE ANTI-PATTERN: carries the Narrator suffix (it is the single home
for "what does this Part-domain event say on the audit feed") but, unlike a
pure Narrator, also performs the write. Splitting text-composition from the
write would just relocate the same one-line call with no real decoupling
benefit, since callers already pass a fully composed message from their own
Narrator (PartRevisionNarrator, AliasNarrator, SupplierItemNarrator).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.events.control_layer.managers.activity_thread_manager import ActivityThreadManager
from app.events.models import ActivityThread
from app.parts.control_layer.thread_domain import default_domain_id_for

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.events.control_layer.handlers.comment_handler import CommentResult
    from app.parts.models import Part, PartRevision, SupplierItem


class PartActivityNarrator:
    def __init__(self, part: "Part", actor: "AbstractUser | None" = None) -> None:
        self.part = part
        self.actor = actor

    def record(self, message: str) -> "CommentResult | None":
        """Post one machine comment onto the base Part thread. No-op on empty."""
        if not message:
            return None
        return ActivityThreadManager(
            self.part,
            self.actor,
            thread_attr="documents_thread",
            domain_id_resolver=lambda: default_domain_id_for(ActivityThread),
        ).add_comment(message, is_human_made=False)

    # -- resolvers: build the narrator from any child, up to its base Part --- #

    @classmethod
    def for_part(cls, part: "Part", actor: "AbstractUser | None" = None) -> "PartActivityNarrator":
        return cls(part, actor)

    @classmethod
    def for_revision(
        cls, revision: "PartRevision", actor: "AbstractUser | None" = None
    ) -> "PartActivityNarrator":
        from app.parts.control_layer.domain_structs.reverse_structs.revision_activity_struct import (
            RevisionActivityStruct,
        )

        return cls(RevisionActivityStruct.from_instance(revision).part, actor)

    @classmethod
    def for_supplier_item(
        cls, item: "SupplierItem", actor: "AbstractUser | None" = None
    ) -> "PartActivityNarrator":
        from app.parts.control_layer.domain_structs.reverse_structs.supplier_item_activity_struct import (
            SupplierItemActivityStruct,
        )

        return cls(SupplierItemActivityStruct.from_instance(item).part, actor)
