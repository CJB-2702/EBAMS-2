"""In-process listener registry.

The whole point of the registry over a Django signal: "what listens to purchase
orders" is answerable by reading this file and whatever calls register().
Currently, nothing does.
"""

from __future__ import annotations

from app.procurement.presentation_layer.tools.po_events.listener import (
    PurchaseOrderEventListener,
)

_LISTENERS: list[PurchaseOrderEventListener] = []


def register(listener: PurchaseOrderEventListener) -> None:
    if listener not in _LISTENERS:
        _LISTENERS.append(listener)


def unregister(listener: PurchaseOrderEventListener) -> None:
    if listener in _LISTENERS:
        _LISTENERS.remove(listener)


def registered_listeners() -> tuple[PurchaseOrderEventListener, ...]:
    return tuple(_LISTENERS)


def clear() -> None:
    """Test hook."""
    _LISTENERS.clear()
