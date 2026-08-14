"""PartBulkUploadAdaptor — the /parts/bulk-upload/ paste-grid POST -> row dicts.

The grid is serialized client-side into a single JSON array (one object per
row) posted as ``rows_json``, since an Excel-paste grid has a variable number
of rows and per-cell POST keys would be awkward to index reliably.
"""

from __future__ import annotations

import json


class PartBulkUploadAdaptor:
    @staticmethod
    def from_post(post) -> list[dict]:
        raw = post.get("rows_json") or "[]"
        try:
            rows = json.loads(raw)
        except (TypeError, ValueError):
            return []
        if not isinstance(rows, list):
            return []

        parsed = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            entry = {
                "part_number": (row.get("part_number") or "").strip(),
                "name": (row.get("name") or "").strip(),
                "part_type": (row.get("part_type") or "").strip(),
                "category": (row.get("category") or "").strip(),
                "description": (row.get("description") or "").strip(),
                "manufacturer": (row.get("manufacturer") or "").strip(),
                "manufacturer_part_number": (row.get("manufacturer_part_number") or "").strip(),
            }
            # Skip fully blank rows (trailing empty rows left in the grid).
            if any(entry.values()):
                parsed.append(entry)
        return parsed

    @staticmethod
    def domain_ids_from_post(post) -> list[int]:
        return [int(v) for v in post.getlist("domain_ids") if v.strip().isdigit()]
