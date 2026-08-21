---
okf_version: "0.1"
type: "Standard"
title: "OKF Documentation Metadata Standard"
description: "Metadata requirements for all documentation files under docs/ — creation date, creator, last-edited date, and editor tracking."
tags: [okf, documentation, metadata, standard]
created: 2026-08-20
created_by: Christian Bissett
updated: 2026-08-20
updated_by: Christian Bissett
---

# OKF Documentation Metadata Standard

All documentation files under `docs/` must include YAML frontmatter with creation and update metadata. This enables traceability, helps agents understand document freshness, and supports documentation maintenance workflows.

## Required Fields

Every `docs/` file must include:

```yaml
---
created: YYYY-MM-DD
created_by: Author Name
updated: YYYY-MM-DD
updated_by: Editor Name
---
```

### Field Definitions

| Field | Type | Purpose |
|-------|------|---------|
| `created` | ISO 8601 date (YYYY-MM-DD) | Date the file was first written |
| `created_by` | String | Name of the person who created the file |
| `updated` | ISO 8601 date (YYYY-MM-DD) | Date of the most recent edit |
| `updated_by` | String | Name of the person who last edited the file |

## Examples

**New documentation file:**
```yaml
---
created: 2026-08-20
created_by: Christian Bissett
updated: 2026-08-20
updated_by: Christian Bissett
---

# My New Document

Content here...
```

**Existing file edited later:**
```yaml
---
created: 2026-08-15
created_by: Jane Doe
updated: 2026-08-20
updated_by: Christian Bissett
---

# Previously Written Document

Updated content here...
```

## Application

- **Apply to all new files** written under `docs/` from this date forward.
- **Apply when editing existing files** — update the `updated` and `updated_by` fields each time the file is substantially modified.
- **Do not retroactively add metadata** to files created before this standard. Historical files retain their current state.
- **If a file has multiple editors over time**, always update to the most recent editor. The `created_by` field never changes after creation.

## Rationale

This metadata serves three purposes:

1. **Traceability** — Documents which human author is responsible for each file and when it was last touched.
2. **Freshness signals** — Agents and readers can assess whether documentation may be stale or requires review.
3. **Maintenance workflows** — Future tooling (linting, documentation audits, change tracking) can leverage these fields for automated checks.

These fields are part of the broader [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf) adoption for this project's documentation layer.
