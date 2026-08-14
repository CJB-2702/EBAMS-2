"""PartCreationWizardAdaptor — the /parts/new/ wizard POST -> PartCreationWizardFactory input."""

from __future__ import annotations

from app.parts.control_layer.adapters.form_parsing import parse_checkbox, parse_int


class PartCreationWizardAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "identity": {
                "part_number": (post.get("part_number") or "").strip(),
                "name": (post.get("name") or "").strip(),
                "description": (post.get("description") or "").strip(),
                "part_type": (post.get("part_type") or "").strip(),
                "category": (post.get("category") or "").strip(),
                "is_active": parse_checkbox(post, "is_active"),
            },
            "domains": {
                "template_id": parse_int(post.get("domain_template_id")),
                "domain_ids": [
                    int(v) for v in post.getlist("domain_ids") if v.strip().isdigit()
                ],
            },
            "supplier_items": PartCreationWizardAdaptor._supplier_item_rows(post),
        }

    @staticmethod
    def _supplier_item_rows(post) -> list[dict]:
        count = parse_int(post.get("supplier_item_count")) or 0
        rows = []
        for i in range(count):
            prefix = f"supplier_items-{i}-"
            mpn = (post.get(f"{prefix}manufacturer_part_number") or "").strip()
            if not mpn:
                continue
            rows.append(
                {
                    "part_manufacturer_id": parse_int(post.get(f"{prefix}part_manufacturer_id")),
                    "manufacturer_part_number": mpn,
                    "name": (post.get(f"{prefix}name") or "").strip(),
                    "description": (post.get(f"{prefix}description") or "").strip(),
                }
            )
        return rows
