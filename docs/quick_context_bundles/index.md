---
okf_version: "0.1"
type: "Index"
title: "Quick Context Bundles"
description: "Per-application loaders that run the codebase mapping script to pull model/control-layer class context on demand."
tags: [quick-context, context-scaling, index, okf]
context_tier: 1
personas: [backend]
---

# Quick Context Bundles

Each file, when referenced with `@`, triggers `python dev_tools/get_models_and_control.py` for one application — either the full app or models-only.

- [Administration (Full Application)](administration.md) / [Administration (Models Only)](administration-models.md)
- [Assets (Full Application)](assets.md) / [Assets (Models Only)](assets-models.md)
- [Events (Full Application)](events.md) / [Events (Models Only)](events-models.md)
- [Public App (Full Application)](public_app.md) / [Public App (Models Only)](public_app-models.md)
