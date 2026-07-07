"""RelationshipPolicy — structural guard for asset parent/child attaches.

Decides whether one asset may become a child of another. The check is purely
structural: an asset may not be its own parent, and may not be attached beneath
one of its own descendants (which would create a loop). Domain and asset class
never gate an attach — this tool deliberately allows cross-domain, cross-class
grouping (e.g. a tank under a set of scuba gear, a trailer under a truck).

This is the single source of truth for what a legal attach is, so the manager
and any future tooling agree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.assets.models import Asset


class RelationshipError(Exception):
    pass


class RelationshipPolicy:
    @staticmethod
    def check_attach(child: "Asset", new_parent: "Asset | None") -> None:
        """Raise ``RelationshipError`` if ``child`` may not be attached under
        ``new_parent``. ``new_parent is None`` (detach to root) is always legal."""
        if new_parent is None:
            return

        if child.id == new_parent.id:
            raise RelationshipError("An asset cannot be its own parent.")

        # Cycle guard: walk new_parent's ancestry; if child appears, the attach
        # would put an asset inside its own structure.
        node = new_parent
        seen: set[int] = set()
        while node is not None:
            if node.id == child.id:
                raise RelationshipError(
                    f"'{child.name}' is already part of '{new_parent.name}'s structure — "
                    "attaching it here would create a loop."
                )
            if node.id in seen:
                break
            seen.add(node.id)
            node = node.parent_asset
