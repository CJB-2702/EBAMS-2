"""AssetRelationshipManager — parent/child relationship write path.

Constructed for the asset whose children are being managed (the *parent*), the way
the relationship edit screen thinks. Exposes intention-revealing verbs —
``attach_child`` / ``detach_child`` — that each, in one transaction:

  1. guard the move structurally (``RelationshipPolicy``: no self-parent, no cycle),
  2. reparent the child (set ``parent_asset`` / recompute ``root_asset`` + ``depth``),
  3. cascade the new root + depth to the child's whole subtree,
  4. write the structured ``AssetParentHistory`` audit row,
  5. emit one ``Event`` linked to BOTH assets via ``AssetEvent`` (roles parent/child).

This is the single write path for relationships — ``AssetContext.reparent`` routes
through it too. This tool is for grouping assets together in small sets (a tank
under scuba gear, a trailer under a truck); it is not a bill-of-materials engine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from app.assets.control_layer.guards.relationship_guard import (
    RelationshipError,
    RelationshipPolicy,
)
from app.assets.control_layer.narrators.asset_event_narrator import AssetEventNarrator
from app.assets.models import Asset, AssetParentHistory
from app.assets.models.core.asset_event import AssetEvent
from app.events.models import Event, EventStatus, EventType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AssetRelationshipManager:
    def __init__(self, parent: "Asset", actor: "AbstractUser") -> None:
        self.parent = parent
        self.actor = actor

    # ── Verbs ────────────────────────────────────────────────────────────────
    def attach_child(self, child_id: int) -> None:
        """Attach the asset ``child_id`` as a child of ``self.parent``. If the
        child already has a parent this is a move; its subtree travels with it."""
        child = Asset.objects.select_related("parent_asset", "asset_class").get(id=child_id)
        RelationshipPolicy.check_attach(child, self.parent)
        self._move(child, self.parent)

    def detach_child(self, child_id: int) -> None:
        """Detach a direct child of ``self.parent``; it becomes its own root and its
        subtree is re-rooted onto it."""
        child = Asset.objects.select_related("parent_asset").get(id=child_id)
        if child.parent_asset_id != self.parent.id:
            raise RelationshipError(
                f"'{child.name}' is not a child of '{self.parent.name}'."
            )
        self._move(child, None)

    # ── Internals ────────────────────────────────────────────────────────────
    def _move(self, child: Asset, new_parent: "Asset | None") -> None:
        attached = new_parent is not None
        # The other asset named on the timeline entry: the new parent on attach,
        # the former parent on detach.
        counterpart = new_parent if attached else child.parent_asset

        old_depth = child.depth_from_root or 0
        if attached:
            new_parent_id = new_parent.id
            new_root_id = new_parent.root_asset_id or new_parent.id
            new_depth = (new_parent.depth_from_root or 0) + 1
        else:
            new_parent_id = None
            new_root_id = child.id
            new_depth = 0

        with transaction.atomic():
            AssetParentHistory.objects.create(
                asset=child,
                previous_parent_asset_id=child.parent_asset_id,
                new_parent_asset_id=new_parent_id,
                previous_root_asset_id=child.root_asset_id,
                new_root_asset_id=new_root_id,
                previous_depth=child.depth_from_root,
                new_depth=new_depth,
                created_by=self.actor,
                updated_by=self.actor,
            )

            child.parent_asset_id = new_parent_id
            child.root_asset_id = new_root_id
            child.depth_from_root = new_depth
            child.updated_by = self.actor
            child.save(
                update_fields=[
                    "parent_asset", "root_asset", "depth_from_root",
                    "updated_by", "updated_at",
                ]
            )

            self._cascade_subtree(child, new_depth - old_depth)
            self._emit_event(counterpart, child, attached=attached)

    def _cascade_subtree(self, moved: Asset, depth_delta: int) -> None:
        """Re-root every descendant of ``moved`` onto the new root and shift its
        depth by the same delta the moved node shifted. Relative depths within the
        subtree are preserved, so one delta applies to the whole branch."""
        new_root_id = moved.root_asset_id
        now = timezone.now()
        frontier = [moved.id]
        while frontier:
            descendants = list(Asset.objects.filter(parent_asset_id__in=frontier))
            if not descendants:
                break
            for node in descendants:
                node.root_asset_id = new_root_id
                node.depth_from_root = (node.depth_from_root or 0) + depth_delta
                node.updated_by = self.actor
                node.updated_at = now
            Asset.objects.bulk_update(
                descendants,
                ["root_asset", "depth_from_root", "updated_by", "updated_at"],
            )
            frontier = [node.id for node in descendants]

    def _emit_event(self, counterpart: "Asset | None", child: Asset, *, attached: bool) -> None:
        if attached:
            title, description = AssetEventNarrator.child_attached(counterpart, child)
        else:
            title, description = AssetEventNarrator.child_detached(counterpart, child)

        event = Event.objects.create(
            domain_id=child.domain_id,
            title=title,
            description=description,
            event_type=EventType.ASSET_MANAGEMENT,
            status=EventStatus.COMPLETE,
            created_by=self.actor,
            updated_by=self.actor,
        )
        AssetEvent.objects.create(
            asset=child, event=event, role="child",
            created_by=self.actor, updated_by=self.actor,
        )
        if counterpart is not None:
            AssetEvent.objects.create(
                asset=counterpart, event=event, role="parent",
                created_by=self.actor, updated_by=self.actor,
            )
