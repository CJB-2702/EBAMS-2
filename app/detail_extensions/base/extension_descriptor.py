"""Extension descriptor contract — the declarative core of the detail_extensions framework.

Each extension package exposes one ``DetailExtension`` subclass that bundles the
unit's identity, target, cardinality, primary table, factory, and manifest. The host
(Asset / AssetModel) never imports an extension's model — it discovers extensions
through the registry of these descriptors.

Minimum contract (per kit D4/D5): ``target`` + ``cardinality``.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import Model

    from app.detail_extensions.base.extension_factory import ExtensionFactory
    from app.detail_extensions.base.manifest import ExtensionManifest


class ExtensionTarget(str, Enum):
    """What an extension attaches to."""

    ASSET = "asset"
    MODEL = "model"

    @property
    def owner_field(self) -> str:
        """The FK field name on the extension's primary table for this target."""
        return "asset" if self is ExtensionTarget.ASSET else "model"


class ExtensionCardinality(str, Enum):
    """How many rows of an extension one owner may carry."""

    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"


class DetailExtension:
    """Base extension descriptor. Subclass per extension package and set the class
    attributes; the framework reads them — it never instantiates the extension.

    Behavior is bound to the class, not to caller-passed flags (kit D5).
    """

    #: Stable identifier used in enablement rows (``extension_key``) and the registry.
    key: str = ""
    #: Human-readable label (for narration / UI).
    label: str = ""
    #: ASSET or MODEL.
    target: ExtensionTarget = ExtensionTarget.ASSET
    #: ONE_TO_ONE (single record) or ONE_TO_MANY (history).
    cardinality: ExtensionCardinality = ExtensionCardinality.ONE_TO_ONE
    #: The concrete primary table class for this extension.
    primary_model: "type[Model] | None" = None
    #: Optional ExtensionFactory subclass; the base factory is used when None.
    factory: "type[ExtensionFactory] | None" = None
    #: File manifest for this extension (required, E5).
    manifest: "ExtensionManifest | None" = None

    # ── Reserved seams (declared but unused this phase) ──────────────────────
    #: Template path for the owner-page card — wired in a later UI phase.
    card_template: str | None = None
