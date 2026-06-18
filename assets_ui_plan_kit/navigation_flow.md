# Navigation & Flow

How the 36 pages connect: the shell, the sidebar, the click-flows, and the
anatomy of the centerpiece Asset-360 page. This is the document to review for
**flow + page structure**.

## App shell (cloned from the events app)

Every page extends `asset_base.html`, a near-copy of
[`ev_base.html`](../app/events/templates/events/ev_base.html):

```
┌─ topnav (current_app_group="Assets") ───────────────────────────────┐
├──────────┬──────────────────────────────────────────────────────────┤
│ sidebar  │  app-container (max 1200px)                               │
│ (220px,  │   breadcrumb                                              │
│  collap- │   messages                                               │
│  sable)  │   #asset-main-content   ← HTMX boost target              │
│          │     page-hero (title + actions)                          │
│          │     body-grid (cards / rail)                             │
└──────────┴──────────────────────────────────────────────────────────┘
```

- Sidebar `<nav>` uses `hx-boost` + `hx-target="#asset-main-content"` +
  `hx-select="#asset-main-content"` + `hx-push-url="true"` (same as events).
- F5 rule: each page also renders standalone.

## Sidebar structure

```
ASSETS                          ← section label
  ▸ Assets Dashboard            /assets/

CORE
  ▸ Assets                      /assets/assets/
  ▸ Asset Models                /assets/models/
  ▸ Asset Classes               /assets/classes/
  ▸ Manufacturers               /assets/manufacturers/
  ▸ Meter History               /assets/meter-history/

CAPABILITIES
  ▸ Definitions                 /assets/capabilities/definitions/
  ▸ By Asset Class              /assets/capabilities/by-class/
  ▸ By Model                    /assets/capabilities/by-model/
  ▸ By Asset                    /assets/capabilities/by-asset/

CONFIGURATIONS
  ▸ Templates                   /assets/configurations/templates/
  ▸ Defined Modifications       /assets/configurations/modifications/

OTHER PORTALS
  ▸ Events                      /events/
  ▸ Administration              /administration/
  ▸ Home                        /
```



## Primary click-flows

### Flow A — Find & inspect an asset (the main loop)
```
Dashboard ──▶ Asset List ──(filter by domain/class/status)──▶ Asset-360
   │                                                            │
   │                                                            ├─▶ Edit ──▶ back to 360
   │                                                            ├─▶ Images Manager
   │                                                            ├─▶ Configuration View ──▶ Configuration Edit
   │                                                            └─▶ Events (events app)
   └──▶ Create Asset (class ▸ model ▸ identity ▸ domain) ──▶ new Asset-360
```

### Flow B — Define the catalog (admin-ish setup)
```
Class List ──▶ Class Detail ──▶ assign Class Capabilities
   ▼
Model List ──▶ Model Detail ──▶ assign Model Capabilities
                  └─▶ Configuration Templates (for this model)
   ▼
Manufacturer List ──▶ Manufacturer Detail (models produced)
```

### Flow C — Capabilities management
```
Capability Definitions ──▶ Definition Form
        │
        ├─▶ By Asset Class  (assign def → class)
        ├─▶ By Model        (assign def → model)
        └─▶ By Asset        (assign def → asset, with qty/notes)
                 └─ resolved capability set shown as a card on each detail page
```

### Flow D — Configuration lifecycle
```
Defined Modifications (catalog) ──▶ Config Template Builder ──▶ Template Detail
                                                                     │
Asset-360 ──▶ Asset Configuration View ──▶ Asset Configuration Edit ─┘
            (apply modifications from a template, set verification status)
```

## Asset-360 card anatomy

The single most important screen. Old layout (`core/assets/detail.html`) used a
3fr/1fr main+sidebar grid; the new mock keeps that via `body-grid has-rail`.

```
page-hero:  [icon] {asset.name}              [Edit] [Images] [⋯]
            serial {serial_number} · {class} · {model} · status tag
            capability_status tag (Operational / Limited / Down)

body-grid (has-rail)
┌─ MAIN (3fr) ─────────────────────────────┐ ┌─ RAIL (1fr) ──────────────┐
│ ▸ Identity & Status                      │ │ ▸ Data Domain             │
│     name, serial, class, model,          │ │   (replaces old Location) │
│     domain, is_active, tags              │ │                           │
│ ▸ Meters (meter1..4 + units)             │ │ ▸ Quick Actions           │
│ ▸ Image Carousel (AssetImage, primary)   │ │   Edit / Add Event /      │
│ ▸ Capabilities (resolved: class⊕model⊕   │ │   New Config              │
│     asset, with qty/notes)               │ │                           │
│ ▸ Current Configuration (template +      │ │                           │
│     verification status) → view/edit     │ │                           │
│                                          │ │                           │
│                                          │ │ ▸ Events (link to /events)│
└──────────────────────────────────────────┘ └───────────────────────────┘
```

Mapping to old → new sources:
- "Location Details" card → **Data Domain** card (`asset.domain`).
- "Make/Model Details" → **Model** + its **Manufacturers** (M2M).
- "Asset Class Details" → **Class** + resolved capabilities.
- New cards with no old equivalent: **Capability-status** rollup tag.

## Density & format

Follows the repo `format=` contract (condensed / medium / large). The mock
implements **medium** by default for list rows and detail cards; condensed
variants are optional stretch and not required for the review build.
</content>
