"""RevisionEditAdaptor — HTTP POST payload -> PartRevisionManager.update input."""

from __future__ import annotations

import datetime


class RevisionEditAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        date_str = (post.get("date_of_release") or "").strip()
        date_of_release = None
        if date_str:
            try:
                date_of_release = datetime.date.fromisoformat(date_str)
            except ValueError:
                date_of_release = None
        return {
            "major_name": (post.get("major_name") or "").strip() or None,
            "minor_name": (post.get("minor_name") or "").strip() or None,
            "summary": (post.get("summary") or "").strip(),
            "notes": (post.get("notes") or "").strip(),
            "date_of_release": date_of_release,
        }
