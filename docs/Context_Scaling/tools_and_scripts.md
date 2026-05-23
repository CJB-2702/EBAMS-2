# Dynamic Context Tools & Scripts

## Codebase Mapping Script (Tier 4)

Generates a compact structural summary of a target directory. Designed for low context cost — output is metadata, not source code.

* **Input:** Directory path string, or a list of paths from a domain skeleton bundle.
* **Output:**
  1. Visual file tree.
  2. Public classes per module.
  3. Extracted docstrings for each class and major service method.
* **Execution rule:** Run this script **before** reading any source files into context. The script output is the lightweight entry point; raw files are the fallback for deep dives only.
* **Manual invocation is fine.** No automation required — the rule is simply that it runs first.

---

## Docs Directory Crawler

Targets the `docs/` folder and regenerates `skeleton.md`. It is the **only mechanism** that writes to `skeleton.md`.

* **Trigger:** Run whenever any file is created or removed under `docs/`.
* **Rule:** Do not manually edit `skeleton.md` or read it to verify correctness — trust the script output entirely.
* **Output:** Replaces `skeleton.md` with a freshly generated index of every file under `docs/`, grouped by tier, with one-line descriptions derived from each file's first heading or opening sentence.

See [skeleton_spec.md](skeleton_spec.md) for the expected output format and structure rules.
