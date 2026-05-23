# Division → Organization map

This document lists every **division** in the application and the **organizations** that belong to it. It is a **human-maintained** reference used for onboarding and audit. For the conceptual rules around the hierarchy (and its informational-only status), see [../Authorization/data_ownership.md](../Authorization/data_ownership.md).

A skeleton of this file can be regenerated from the current database with:

```bash
python dev_tools/build_org_chart_skeleton.py
```

That script writes skeletons without overwriting human edits. Review the diff and merge manually.

---

## Divisions

*(Populate by running `build_org_chart_skeleton.py` and reviewing the output. The seed data ships with two divisions — North and South — each with two organizations.)*

- **North Division** (`north`)
  - North Acme Ltd
  - North Beta Inc
- **South Division** (`south`)
  - South Acme Ltd
  - South Beta Inc
