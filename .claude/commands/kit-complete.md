---
description: Archive a completed starter kit or project to docs/technical_decisions/project_history and log it with a completion summary.
argument-hint: "<kit-name> <summary> — kit-name is the directory name (e.g. asset_control_layer_starter_kit); summary is a brief description of what was completed"
---

Moves a completed starter kit from its current location to `docs/technical_decisions/project_history/` and appends a timestamped entry to `project_history.md`.

**Usage:**

```bash
/kit-complete asset_control_layer_starter_kit "Built control layer handlers and validators for asset domain"
```

**What it does:**

1. Validates the kit directory exists in the current location
2. Moves it to `docs/technical_decisions/project_history/<kit-name>/`
3. Appends a summary entry with today's date to `docs/technical_decisions/project_history/project_history.md`
4. Prints confirmation of the archive

**Entry format in project_history.md:**

```
| 2026-06-08 | asset_control_layer_starter_kit | Built control layer handlers and validators for asset domain |
```

---

**Implementation (Bash):**

```bash
#!/bin/bash
set -e

KIT_NAME="${1:?Kit name required (e.g., asset_control_layer_starter_kit)}"
SUMMARY="${2:?Summary required (e.g., \"Built control layer handlers\")}"

SOURCE_PATH="${KIT_NAME}"
DEST_DIR="docs/technical_decisions/project_history"
DEST_PATH="${DEST_DIR}/${KIT_NAME}"
HISTORY_FILE="${DEST_DIR}/project_history.md"
TODAY=$(date +%Y-%m-%d)

# Check source exists
if [ ! -d "$SOURCE_PATH" ]; then
    echo "Error: Kit directory '$SOURCE_PATH' not found"
    exit 1
fi

# Check history file exists
if [ ! -f "$HISTORY_FILE" ]; then
    echo "Error: History file '$HISTORY_FILE' not found"
    exit 1
fi

# Move kit to project history
mkdir -p "$DEST_DIR"
mv "$SOURCE_PATH" "$DEST_PATH"

# Append entry to history (insert before closing marker or end of file)
# Format: | DATE | KIT_NAME | SUMMARY |
ENTRY="| $TODAY | $KIT_NAME | $SUMMARY |"

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
