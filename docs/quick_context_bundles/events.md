# Quick Context Bundle: Events (Full Application)

When this file is referenced or included in the conversation (e.g., using `@`), you must execute the following command to load the class/docstring context for the `events` application:

```bash
python dev_tools/get_models_and_control.py --application events
```

Read the full YAML output of the command. It lists every Python class with its docstring, and records non-Python files as present-only.
Use this as a context summary — do not re-read individual files unless implementation details are requested. Briefly confirm which layers/directories were found and how many classes total.
