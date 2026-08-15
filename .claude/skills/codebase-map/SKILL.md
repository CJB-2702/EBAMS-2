---
name: codebase-map
description: Generate a compact structural map (file tree + class names + class docstrings, no method bodies) of a Django sub-app or directory before exploring it. Use this FIRST whenever a task requires finding "where is X" or "what exists in this app" across more than one or two files — before reaching for grep/Glob/Explore across app/<sub-app>/. Cheap, low-context, and read-only.
---

# Codebase map

This is the Tier 4 "Automated Overview" tool described in
[harness/Context_Scaling/tools_and_scripts.md](../../../harness/Context_Scaling/tools_and_scripts.md).
It wraps `dev_tools/get_classes_and_descriptions.py` (generic) and
`dev_tools/get_models_and_control.py` (Django-app-scoped convenience wrapper).

**Run this before grepping around an unfamiliar app or directory.** It gives
a YAML structural summary — file tree, class names, class docstrings — for a
fraction of the tokens a broad grep sweep or a string of speculative file
reads costs, and it tells you which file to open next instead of making you
guess from filenames alone.

## When to use

- Starting a task in a sub-app you haven't already loaded context for this
  session ("where does X live in procurement", "what handlers exist for
  shipments", "is there already a guard for this").
- Before writing a new class, to check whether something similar already
  exists in the target directory.
- As the first step of any exploration that would otherwise be "grep for a
  keyword across `app/<sub-app>/`" — run the map first, then grep/read only
  the specific files the map points to.

## When NOT to use

- You already know the exact file (a path was given, or you loaded it
  earlier this session) — just Read it.
- You're searching for a literal string/usage across the *whole* repo
  (e.g. "who calls `PartDemandStateManager.transition`") — that's a job for
  grep, not a structural map. The map shows what classes exist, not who
  references them.
- Templates, migrations, and static assets — the script skips non-`.py`
  structure anyway; use Glob/Read for those directly.

## Invocation

Whole sub-app:
```bash
python dev_tools/get_models_and_control.py --application procurement
```

Models only (fastest, narrowest):
```bash
python dev_tools/get_models_and_control.py --application procurement --models_only
```

Arbitrary directory (not just `app/<name>` roots), e.g. one layer deep:
```bash
python dev_tools/get_classes_and_descriptions.py --path app/procurement/control_layer
```

Add `--file <path>` to either to write the YAML to a file instead of stdout
(useful if you want to keep the map around while you work rather than
re-running it).

## Reading the output

Each entry is `path`, optional `files` (with `classes: [{name, docstring}]`
for `.py` files that have any), and optional `subdirectories` (recursive).
Files/classes with no docstring still appear — an empty docstring in the
output means "open the file, there's no summary to go on." Dunder/underscore-
prefixed entries (`__init__.py`, `__pycache__`) are skipped by the script.

## After mapping

Once the map shows which file(s) are relevant, Read those specific files —
don't stop at the docstring summary for anything you're about to modify.
