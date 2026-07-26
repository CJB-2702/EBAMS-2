---
description: Archive a completed starter kit or project to docs/<app-name>/project_history/ and log it in the shared master index.
argument-hint: "<app-name> <kit-name> <summary> — app-name is the owning application's docs folder (e.g. assets); kit-name is the directory name (e.g. asset_control_layer_starter_kit); summary is a brief description of what was completed"
---

Moves a completed **starter kit** from its current location to `docs/<app-name>/project_history/` and appends a timestamped entry to the shared master index at `docs/technical_decisions/project_history.md`.

> **Starter kits only.** Do not archive a `front-end-kit/<topic>/` folder — front-end kits are declared disposable and are **deleted** once the UI is built, not preserved. Git history keeps them if anyone needs to look back.

**Usage:**

```bash
/kit-complete assets asset_control_layer_starter_kit "Built control layer handlers and validators for asset domain"
```

**What it does:**

1. Validates the kit directory exists in the current location
2. Moves it to `docs/<app-name>/project_history/<kit-name>/`
3. Appends a summary entry with today's date to `docs/technical_decisions/project_history.md`
4. Prints confirmation of the archive

**Entry format in project_history.md:**

```
| 2026-06-08 | assets | asset_control_layer_starter_kit | Built control layer handlers and validators for asset domain |
```

---

**Implementation (Bash):**

```bash
#!/bin/bash
set -e

APP_NAME="${1:?App name required (e.g., assets — the docs/<app-name>/ this kit belongs to)}"
KIT_NAME="${2:?Kit name required (e.g., asset_control_layer_starter_kit)}"
SUMMARY="${3:?Summary required (e.g., \"Built control layer handlers\")}"

SOURCE_PATH="${KIT_NAME}"
DEST_DIR="docs/${APP_NAME}/project_history"
DEST_PATH="${DEST_DIR}/${KIT_NAME}"
HISTORY_FILE="docs/technical_decisions/project_history.md"
TODAY=$(date +%Y-%m-%d)

# Check source exists
if [ ! -d "$SOURCE_PATH" ]; then
    echo "Error: Kit directory '$SOURCE_PATH' not found"
    exit 1
fi

# Check owning app folder exists
if [ ! -d "docs/${APP_NAME}" ]; then
    echo "Error: App folder 'docs/${APP_NAME}' not found"
    exit 1
fi

# Check history file exists
if [ ! -f "$HISTORY_FILE" ]; then
    echo "Error: History file '$HISTORY_FILE' not found"
    exit 1
fi

# Move kit to the owning app's project history
mkdir -p "$DEST_DIR"
mv "$SOURCE_PATH" "$DEST_PATH"

# Append entry to the shared master history (insert before closing marker or end of file)
# Format: | DATE | APP_NAME | KIT_NAME | SUMMARY |
ENTRY="| $TODAY | $APP_NAME | $KIT_NAME | $SUMMARY |"

# Find the line with "<!-- Kit-complete entries" and insert after it
if grep -q "<!-- Kit-complete entries" "$HISTORY_FILE"; then
    # Insert after the comment line
    sed -i "/<!-- Kit-complete entries/a\\
$ENTRY" "$HISTORY_FILE"
else
    # Fallback: append before closing marker or at end
    sed -i "/^## Completed Projects/a\\
$ENTRY" "$HISTORY_FILE"
fi

echo "✓ Archived $KIT_NAME to $DEST_PATH"
echo "✓ Added entry to $HISTORY_FILE:"
echo "  $ENTRY"
```
