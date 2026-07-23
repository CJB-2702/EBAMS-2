"""SupplierVendorRevisionManager — records a vendor revision as one
append-only Comment on the item's thread (D13). Not a revision row."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.events.control_layer.managers.activity_thread_manager import ActivityThreadManager
from app.parts.models import SupplierItem

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.events.control_layer.handlers.comment_handler import CommentResult


class SupplierVendorRevisionManager:
    def __init__(self, item_id: int, actor: "AbstractUser | None" = None) -> None:
        self.item = SupplierItem.objects.get(id=item_id)
        self.actor = actor

    def record(self, *, vendor_revision_id: str, note: str = "", domain_id: int) -> "CommentResult":
        body = json.dumps(
            {
                "vendor_revision_history": {
                    "vendor_revision_id": vendor_revision_id,
                    "note": note,
                }
            }
        )
        return ActivityThreadManager(self.item, self.actor).add_comment(
            body, domain_id=domain_id
        )

    def list(self) -> list[dict]:
        comments = ActivityThreadManager(self.item, self.actor).comments()
        history = []
        for c in comments:
            try:
                payload = json.loads(c["body"])
            except (ValueError, TypeError):
                continue
            entry = payload.get("vendor_revision_history")
            if entry:
                history.append({**entry, "created_at": c["created_at"]})
        return history
