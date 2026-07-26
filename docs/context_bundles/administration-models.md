---
type: "Quick Context Bundle"
title: "Quick Context Bundle: Administration (Models Only)"
description: "Read the full YAML output of the command."
tags: [quick-context, quick-context-bundle]
context_tier: 2
---

# Quick Context Bundle: Administration (Models Only)

When this file is referenced or included in the conversation (e.g., using `@`), you must execute the following command to load the class/docstring context for the models of the `administration` application:

```bash
python dev_tools/get_models_and_control.py --application administration --models_only
```

Read the full YAML output of the command. It lists every model class with its docstring.
Use this as a context summary — do not re-read individual files unless implementation details are requested. Briefly confirm which model classes were found.
