#!/usr/bin/env python
"""Emit `docs/DOMAIN/orgchart/` skeletons from the current database.

Writes:

- `docs/DOMAIN/orgchart/divisions.md` — list of divisions with their organizations.
- `docs/DOMAIN/orgchart/<organization-slug>.md` — one per organization, listing its
  sub-domains (data domains linked through `OrganizationDomain`).

Skeletons are safe to regenerate: existing files are overwritten only when the
`--force` flag is passed. Otherwise a `.generated.md` sibling is emitted next to
each existing document so the human-maintained version stays untouched and the
operator can diff/merge manually.

Usage (from repository root):

    python dev_tools/build_org_chart_skeleton.py
    python dev_tools/build_org_chart_skeleton.py --force
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve().parent
    return here.parent if here.name == "dev_tools" else here


def _bootstrap_django() -> None:
    root = _repo_root()
    sys.path.insert(0, str(root / "app"))
    sys.path.insert(0, str(root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()


def _render_divisions_md(divisions) -> str:
    from app.administration.models import DivisionOrganisation

    lines = [
        "# Division → Organization map",
        "",
        "This document lists every **division** in the application and the **organizations** "
        "that belong to it. Regenerate the skeleton from the database with:",
        "",
        "```bash",
        "python dev_tools/build_org_chart_skeleton.py",
        "```",
        "",
        "For conceptual rules see [../admin/DATA_OWNERSHIP.md](../admin/DATA_OWNERSHIP.md).",
        "",
        "---",
        "",
        "## Divisions",
        "",
    ]
    if not divisions:
        lines.append("*(No divisions defined.)*")
    for div in divisions:
        lines.append(f"- **{div.name}** (`{div.slug}`)")
        links = (
            DivisionOrganisation.objects.filter(division=div)
            .select_related("organization")
            .order_by("organization__name")
        )
        if not links:
            lines.append("    - *(no organizations linked)*")
            continue
        for link in links:
            org = link.organization
            lines.append(f"    - {org.name} — see [{org.slug}.md]({org.slug}.md)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Related documents")
    lines.append("")
    lines.append(
        "- [../admin/DATA_OWNERSHIP.md](../admin/DATA_OWNERSHIP.md) — Data Domain primitive and Golden Rule.",
    )
    lines.append("- Per-organization sub-domain documents alongside this file (`<slug>.md`).")
    lines.append("")
    return "\n".join(lines)


def _render_organization_md(org) -> str:
    from app.administration.models import OrganizationDomain

    division = org.division
    div_line = division.name if division is not None else "*(no division assigned)*"

    lines = [
        f"# {org.name}",
        "",
        f"- **Slug:** `{org.slug}`",
        f"- **Division:** {div_line}",
        "",
        "This document lists the **Data Domains** linked to this organization. Regenerate "
        "the skeleton from the database with:",
        "",
        "```bash",
        "python dev_tools/build_org_chart_skeleton.py",
        "```",
        "",
        "For the Data Domain concept see [../admin/DATA_OWNERSHIP.md](../admin/DATA_OWNERSHIP.md).",
        "",
        "---",
        "",
        "## Data Domains",
        "",
    ]

    links = OrganizationDomain.objects.filter(organization=org).select_related("domain").order_by(
        "domain__name",
    )
    if not links:
        lines.append("*(No data domains linked to this organization.)*")
    else:
        for link in links:
            d = link.domain
            lines.append(f"- **{d.name}** (`{d.slug}`)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Related documents")
    lines.append("")
    lines.append("- [divisions.md](divisions.md) — division → organization map.")
    lines.append(
        "- [../admin/DATA_OWNERSHIP.md](../admin/DATA_OWNERSHIP.md) — Data Domain primitive and Golden Rule.",
    )
    lines.append("")
    return "\n".join(lines)


def _write(path: Path, content: str, *, force: bool) -> Path:
    if path.exists() and not force:
        target = path.with_suffix(".generated.md")
    else:
        target = path
    target.write_text(content, encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Build org-chart doc skeletons from the database.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing documents instead of writing .generated.md siblings.",
    )
    args = parser.parse_args()

    _bootstrap_django()
    from app.administration.models import Division, Organization

    root = _repo_root()
    out_dir = root / "docs" / "DOMAIN" / "orgchart"
    out_dir.mkdir(parents=True, exist_ok=True)

    divisions = list(Division.objects.order_by("name"))
    divisions_md = _render_divisions_md(divisions)
    wrote_divisions = _write(out_dir / "divisions.md", divisions_md, force=args.force)

    organizations = list(Organization.objects.order_by("name").prefetch_related("divisions"))
    organization_targets: list[Path] = []
    for org in organizations:
        org_md = _render_organization_md(org)
        organization_targets.append(_write(out_dir / f"{org.slug}.md", org_md, force=args.force))

    print(f"Wrote {wrote_divisions.relative_to(root)}")
    for t in organization_targets:
        print(f"Wrote {t.relative_to(root)}")
    print(
        "\nTip: files ending in .generated.md are skeletons for existing docs. "
        "Diff them against the originals and merge by hand, then delete the .generated sibling.",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
