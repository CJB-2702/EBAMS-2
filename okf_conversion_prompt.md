# Task: Convert the `docs/` repository to Open Knowledge Format (OKF v0.1)

You are adding OKF v0.1 frontmatter to every markdown file under `docs/` in this
Django project. `docs/Architecture/` has ALREADY been converted — treat it as the
canonical reference example and mirror its conventions exactly. Do not modify it.

## What OKF is (you do not need to research this)

OKF v0.1 (Google Cloud) represents knowledge as a directory of markdown files with
YAML frontmatter. Rules that matter here:
- Every non-reserved `.md` file MUST have parseable YAML frontmatter with a
  non-empty `type` field. That is the only hard conformance requirement.
- Recommended fields: `title`, `description`, `tags`. Producers may add custom
  keys; consumers must preserve them.
- Reserved filenames: `index.md` (directory listing / progressive disclosure) and
  `log.md` (change history). The BUNDLE-ROOT `index.md` may declare `okf_version: "0.1"`.
- Cross-links: relative markdown links (so files still browse correctly on GitHub).

## The frontmatter shape to apply

For every existing leaf doc, PREPEND this block. Never modify the body below it.

```yaml
---
type: <see taxonomy>
title: <human-readable title>
description: <one sentence, ends with a period>
tags: [<lowercase>, <topic>, <slugs>]
context_tier: <0-5, see below>
---
```

- `title`: derive from the top `# heading`, cased as a title.
- `description`: one factual sentence summarizing the file, from its opening lines.
- `tags`: 3-5 lowercase hyphenated topic slugs. First tag = section name
  (e.g. `authorization`, `events`, `ux-ui`).
- Do NOT add `resource` or `timestamp` (resource is for external assets; timestamp
  comes from git).
- If a file already starts with `---`, SKIP it (idempotent).

## `type` taxonomy

Use the pattern `<Section> <Kind>`. Established types from the pilot:
`Architecture Guide`, `Architecture Example`, `Vocabulary Reference`,
`Skeleton Bundle`, `Index`.

Extend consistently for other sections, e.g.:
- `docs/Authorization/*.md` → `Authorization Guide`; its `Examples/*` → `Authorization Example`
- `docs/UX_UI/*.md` → `UX Guide`; `Examples/*` → `UX Example`
- `docs/CoreDomain/*`, `docs/Events/*`, `docs/applications/*` → `Domain Doc` / `Domain Example`
- `docs/Development_Tools/*` → `Tooling Guide`
- `docs/Context_Scaling/*` → `Context Scaling Spec`
- `docs/technical_decisions/**` → `Technical Decision`
- `docs/starter_kit_process/*` → `Process Guide`
- Root `docs/*.md` anchors (e.g. `Events.md`, `Authorization.md`) → `Concept Anchor`
- Any `index.md` you create → `Index`

Keep the vocabulary small and reuse existing types before inventing new ones.

## `context_tier` — this project's context-scaling model

Read `docs/Context_Scaling.md`. Map each file to its tier:
- **Tier 1** — root `docs/*.md` concept anchors, and every `index.md`.
- **Tier 2** — `docs/[Concept]/*.md` full specs.
- **Tier 3** — `docs/[Concept]/Examples/*` implementation examples.
Add `context_tier:` to EVERY file (leaf files and index.md).

## `personas` — bundle-level only

Persona routing is FOLDER-granular (see `docs/Context_Scaling/persona_routing.md`).
Do NOT put `personas:` on leaf files. Put it ONLY on each bundle-root `index.md`,
using this controlled vocabulary matching the slash commands exactly:
`backend`, `frontend`, `admin`, `code-architect`, `business`.

Folder → personas mapping:
- `docs/Architecture/*` → `[backend, code-architect]` (already done)
- `docs/UX_UI/*` → `[frontend, code-architect]`
- `docs/Authorization/*` → `[admin]`
- `docs/ApplicationGoals.md` / `docs/applications/*` → `[business]`
- `docs/CoreDomain/*`, `docs/Events/*` → `[backend, business]`
- `docs/Development_Tools/*`, `docs/Context_Scaling/*`,
  `docs/technical_decisions/*`, `docs/starter_kit_process/*` → `[backend]`
For any folder you are unsure about, pick the closest match and note it in your summary.
Only add `personas:` to an individual leaf file if it genuinely deviates from its bundle.

## `index.md` listings (progressive disclosure)

For each concept directory that lacks an `index.md`, create one. Follow the exact
shape of `docs/Architecture/index.md` / `Examples/index.md` / `vocabulary/index.md`:
- Frontmatter: `type: "Index"`, `title`, `description`, `tags`, `context_tier`, and
  (on a bundle root only) `personas` + `okf_version: "0.1"`.
- Body: a short intro + a bulleted list of the directory's files as relative
  markdown links with one-line descriptions, plus links to any sub-bundle `index.md`.
- A directory that already has a `README.md` acting as its overview: keep the README
  as a concept doc, but still add an `index.md` listing (mirror how `vocabulary/`
  was handled in the pilot).
- "Bundle root" = the top folder of a concept section (e.g. `docs/Authorization/`,
  `docs/UX_UI/`). Only bundle roots get `okf_version` + `personas`.

## Workflow

1. Read `docs/Architecture/index.md` and one leaf file (e.g.
   `docs/Architecture/overview.md`) to internalize the exact target shape.
2. Enumerate all `.md` files under `docs/` EXCLUDING `docs/Architecture/**`.
3. For efficiency and correctness, write a Python script that maps each file to its
   frontmatter (mirroring the pilot's approach) and prepends it; skip files that
   already start with `---`. Do not hand-edit 190+ files one at a time.
4. Create the missing `index.md` listings.
5. Do NOT alter any file body. Do NOT change existing horizontal-rule `---` lines
   mid-document. Only prepend frontmatter and create new index files.

## Verify before finishing

Run a conformance check over all of `docs/**`:
- every non-reserved `.md` starts with `---` and has a non-empty `type`;
- every file has a `context_tier`;
- every bundle-root `index.md` has `okf_version: "0.1"` and a valid `personas` list;
- no `personas` value outside the five allowed slugs.
Print the type distribution (`grep -rh '^type:'` | sort | uniq -c) and the count of
files converted. Report any files you skipped or folders where persona/tier was
ambiguous.

## Constraints
- Additive only — bodies untouched, fully reversible, nothing committed.
- Do not touch anything outside `docs/`.
- Idempotent: safe to re-run.
