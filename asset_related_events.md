# Asset-Related Events & `AssetEvent` Model Relocation Summary

## Architectural Context & Problem Statement

Previously, `AssetEvent` was defined under `app/assets/models/core/asset_event.py`. While it provided a junction table between `Asset` and lifecycle `Event` records, defining it inside the `assets` sub-application created several structural limitations:

1. **Inverted Ownership**: Events are generic, domain-scoped records generated across all sub-applications (`maintenance`, `dispatching`, `inventory`/`parts`, `administration`, `assets`). Having the junction table owned solely by the `assets` app prevented other sub-applications from cleanly creating asset-event associations without importing deep internal models from `assets`.
2. **Under-Integration**: Multiple event-generating features across the application (such as maintenance work order completions, vehicle dispatches, receiving parts for assets, and administrative audit trails) created `Event` records but neglected to establish formal `AssetEvent` links to associated equipment.

## Architectural Changes & Relocation

### 1. Model Relocation to `app/events`
`AssetEvent` has now been relocated to `app/events/models/asset_event.py`, making it a core primitive of the central `events` application:

```python
# app/events/models/asset_event.py
class AssetEvent(AuditFieldsMixin):
    """Junction table linking an Asset to a lifecycle Event in the events app.
    
    Owned by the events sub-application so that all modules (maintenance,
    dispatching, inventory, administration, assets) can associate events with assets.
    """
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="asset_events",
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.PROTECT,
        related_name="asset_links",
    )
    role = models.CharField(max_length=50, null=True, blank=True)
```

### 2. Backward Compatibility in `app/assets`
`app/assets/models/core/asset_event.py` now re-exports `AssetEvent` from `app.events.models`, ensuring zero breaking changes for existing code while establishing `app/events/models` as the single canonical source.

### 3. Cross-Application Integration Pattern
With `AssetEvent` housed in `app/events/`:
- **Maintenance**: When a scheduled maintenance plan or work order event completes on an asset, an `AssetEvent` junction row (`role="target_asset"`) is saved alongside the `MaintenanceDetail` record.
- **Dispatching**: When a vehicle or equipment asset is dispatched, an `AssetEvent` junction row (`role="dispatched_asset"`) links the dispatch event to the asset.
- **Inventory & Parts**: When parts are issued or received for a specific asset, an `AssetEvent` junction row (`role="part_recipient"`) links the inventory movement event to the asset.
- **Asset Lifecycle**: Status transitions, acquisitions, smog/registration renewals, and ownership transfers generate `AssetEvent` rows (`role="subject"`) for comprehensive timeline tracking.
- **Administration**: Security and permission updates affecting asset domain access generate audit events linked to the impacted assets.

## Querying Asset Events & Portals

1. **Filtering Events by Asset**:
   `list_events_for_user(user).filter(asset_links__asset_id=asset_id)`
2. **Asset Detail Timeline**:
   An asset's detail page can query `asset.asset_events.select_related('event')` to display a unified lifecycle timeline containing maintenance, dispatch, inventory, and administrative events in a single HTMX stream.
3. **Sub-Application Portals**:
   Each sub-application (`/assets/events/`, `/maintenance/events/`, `/dispatching/events/`, `/parts/events/`, `/administration/events/`) displays domain-filtered event cards using `AssetEvent` links to correlate asset details.
