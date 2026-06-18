# Tech Debt: Assets App Blocked on Parts Infrastructure

**Logged:** 2026-06-09

## Blocker

The assets application is incomplete and cannot be finished until a dedicated **parts** application exists. Assets have child component relationships (e.g., model number, quantity, required flag) that reference part definitions — these are currently read-only mocks in the UI because the underlying part definition and cost tracking models do not exist.

## What is needed

A **parts** application providing:
- Part definition models (model number, description, manufacturer, categorization)
- Cost tracking history (price records over time, supplier linkage)

## Impact on assets

Until the parts app ships:
- The "Child Components" section of asset detail views renders from mock data only
- `asset_handler.py` child-component logic is dead code
- Any asset feature that depends on part lookups (cost rollup, BOM, etc.) cannot be implemented

## Resolution path

Build and ship the parts infrastructure / application first, then return to complete the assets app against real part definitions.
