# Part Demand Source and Event Tracking

## Overview

Part demands in EBAMS-2 serve as the central representation of material needs across the organization. To improve traceability, purchasing aggregation, and issuance grouping, each `PartDemand` records two key metadata attributes:

- **`source`**: The originating functional area/application (e.g. `Procurement`, `Maintenance`, `Dispatching`, `General`).
- **`event_id`**: A foreign key pointing to the underlying `events.Event` detail record that triggered the demand (such as a `MaintenanceDetail` or `DispatchingDetail`).

This tracking architecture provides purchasing officers and inventory managers with direct insight into why a demand was created and allows grouping related part demands when placing Purchase Orders (POs) or issuing inventory from warehouses.

---

## Architectural Principles & Alignment

1. **Decoupled Origin Metadata**: Consumer applications maintain inward-pointing link tables (e.g., `maintenance.PartDemandLink`, `dispatching.DispatchDemandLink`) for domain operations. The `PartDemand` model itself carries `source` and `event_id` purely for high-performance indexing, search filtering, and cross-application grouping without tight model coupling.
2. **Database Indexing**: The `pd_source_event_idx` index on `(source, event_id)` optimizes multi-field queries in procurement demand lists and issuance workflows.
3. **Auditability**: `source` defaults to `Procurement` for standalone requests raised directly within the procurement app. Cross-application managers (such as `PartDemandManager` in Maintenance and `DispatchDemandManager` in Dispatching) explicitly supply their respective `source` and `event_id` upon demand creation.

---

## Technical Details & Data Flow

### 1. Model Schema (`procurement.PartDemand`)

```python
class PartDemand(AuditFieldsMixin):
    source = models.CharField(
        max_length=30,
        choices=DemandSourceModule.choices,
        default=DemandSourceModule.PROCUREMENT,
        help_text="The originating module or system process.",
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="part_demands",
        help_text="Optional event linking this demand to a maintenance or dispatch event.",
    )
```

### 2. Origin Module Population

| Origin | `source` Value | `event_id` Source | Initiating Component |
| :--- | :--- | :--- | :--- |
| **Procurement** | `Procurement` | `None` (Standalone) | `PartDemandCreateAdaptor` / `PartDemandFactory` |
| **Maintenance** | `Maintenance` | `action.event_detail_id` | `PartDemandManager.create_for_action` |
| **Dispatching** | `Dispatching` | `dispatch.pk` | `DispatchDemandManager.raise_demand` |

### 3. Search and UI Filtering

The procurement demand index (`/procurement/demands/`) supports querying demands by `source` and `event_id`. The presentation layer (`OpenDemandSearch.index_list`) accepts these parameters and renders responsive filters and tracking badges in `index.html`, `_results_card.html`, and `detail.html`.
