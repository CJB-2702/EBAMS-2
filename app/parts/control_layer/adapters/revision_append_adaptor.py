"""RevisionAppendAdaptor — HTTP POST payload -> PartRevisionManager input."""

from __future__ import annotations

import datetime

from app.parts.control_layer.adapters.form_parsing import parse_int


class RevisionAppendAdaptor:
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
            "kind": (post.get("kind") or "major").strip(),
            "summary": (post.get("summary") or "").strip(),
            "major_name": (post.get("major_name") or "").strip() or None,
            "minor_name": (post.get("minor_name") or "").strip() or None,
            "date_of_release": date_of_release,
            "major_number": parse_int(post.get("major_number")),
        }
