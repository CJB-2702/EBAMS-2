# Tech Debt: Heuristic Origin Entity Link Resolution & Single Event View Fragment Wrapping

**Date**: 2026-08-20  
**Application**: `app/events`  
**Status**: Deferred / Open for future refactoring  

---

## 1. Context & Implementation

In response to user requirements for navigating from Event cards to originating records (e.g. Asset details, User profiles, Work Orders), `get_event_origin_link()` was introduced in `app/events/presentation_layer/tools/generic_cards.py`. In addition, `ev_detail.html` was refactored to wrap the canonical `events/fragments/event_card.html` template fragment.

Currently, `get_event_origin_link()` inspects proxy detail fields (`detail.asset`, `detail.requested_for`) and `AssetEvent` associations to construct an `{url, label, icon}` dictionary.

---

## 2. Deferred Architectural Improvements & Reversal Plan

### A. Dynamic Attribute Inspection vs. `GenericForeignKey`
- **Current State**: Probes proxy detail attributes using `hasattr(detail, "asset")`, `hasattr(detail, "requested_for")`, and `asset_links`.
- **Ideal State**: Add a formal Django `GenericForeignKey` (`origin_content_type`, `origin_object_id`) to `Event`.
- **Reversal Procedure**:
  1. Add `origin_content_type` and `origin_object_id` fields to `Event` in `app/events/models/event.py`.
  2. Implement `get_absolute_url()` on models (`WorkOrder`, `Dispatch`, `PurchaseOrder`, `Asset`, `User`).
  3. Replace attribute checks in `get_event_origin_link()` with `event.origin_object.get_absolute_url()`.
  4. Template contract (`card.origin_link`) remains 100% identical and requires zero HTML changes.

### B. Single Event Detail Page (`ev_detail.html`) Fragment Unbundling
- **Current State**: `ev_detail.html` embeds `event_card.html` to guarantee 100% feature parity with feed cards (domain colors, detail fragment, comment collapsing, attachment previews).
- **Reversal Procedure**:
  - If single event detail pages require a dedicated multi-column dashboard layout instead of the card shell, `ev_detail.html` can be split back into a standalone page without touching `build_activity_card()`.
