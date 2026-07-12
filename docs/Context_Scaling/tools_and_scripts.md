---
type: "Context Scaling Spec"
title: "Dynamic Context Tools & Scripts"
description: "Generates a compact structural summary of a target directory."
tags: [context-scaling, context-scaling-spec]
context_tier: 2
---

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

