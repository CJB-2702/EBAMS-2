---
type: "Technical Decision"
title: "Multiple `templates/shared/` Folders Collide in Django Template Namespace"
description: "Includes of shared/<something>.html were resolving to the wrong file, or appearing to \"not update\" when the file was edited."
tags: [technical-decisions, technical-decision, incident-history]
context_tier: 2
---

# Multiple `templates/shared/` Folders Collide in Django Template Namespace

- **Date:** 2026-05
- **Affected area:** Any `{% include "shared/<file>.html" %}` reference. Surfaced while trying to share a `shared/dual_listbox.html` fragment across `administration/` partials — see [dual_listbox_template_fragment_attempt.md](dual_listbox_template_fragment_attempt.md).

## What failed

Includes of `shared/<something>.html` were resolving to the wrong file, or appearing to "not update" when the file was edited. Multiple Django apps each had their own `templates/shared/` folder (e.g. `app/administration/templates/shared/...`, `app/public_app/templates/shared/...`, and other sub-apps following the same convention).

Django's `app_directories` template loader walks each installed app's `templates/` directory and registers everything underneath using **paths relative to that `templates/` root**. There is no per-app namespacing of the relative path. So two files in two different apps at:

- `app/administration/templates/shared/dual_listbox.html`
- `app/public_app/templates/shared/dual_listbox.html`

both register as the same logical template name: `shared/dual_listbox.html`. The first one the loader finds — driven by `INSTALLED_APPS` order — wins. The other becomes unreachable by name. Edits to the "losing" file produce no visible change. Renames or moves can silently flip which file resolves. The failure mode is silent: no error, just the wrong markup.

This is not a bug in Django — it is the documented behavior of `app_directories`. It just looks like one because filesystem paths and template names appear identical until you understand the loader is collapsing across apps.

## Root cause

Using a generic, **non-app-namespaced** subfolder name (`shared/`) inside the per-app `templates/` directory of more than one app. The Django template loader concatenates results across apps into one flat name space, so two apps owning `templates/shared/foo.html` collide.

## What changed

- The shared cross-app components were consolidated into **one** owning app's `templates/shared/` directory (currently `public_app/templates/shared/`), and the duplicates under other apps' `templates/shared/` folders were removed.
- The `shared/dual_listbox.html` fragment was retained as a structural reference but is no longer `{% include %}`-ed — see [dual_listbox_template_fragment_attempt.md](dual_listbox_template_fragment_attempt.md).

## Rule going forward

- **Do not** create a `templates/shared/` folder in more than one app. Pick one owning app for cross-app shared partials and put them there.
- The safest naming convention for cross-app shared templates is to namespace them with the owning app: `templates/<owning_app>/<file>.html`, included as `{% include "<owning_app>/<file>.html" %}`. The current consolidation uses the bare `shared/` prefix but only from a single owning app to keep `{% include %}` paths short — this is only safe as long as no other app reintroduces a `templates/shared/` directory.
- App-private partials should live under `templates/<app_name>/...` so they cannot collide with anything.

## Why this is in the decision system

The collision is invisible at the filesystem level — two real files exist, both look correct, only one resolves — and easy to re-introduce by reflex (every app "obviously" can have its own `shared/` folder). Recording this means the next engineer reaches for an app-namespaced subdirectory the first time instead of after a half-day of "why is my edit not showing up?"
