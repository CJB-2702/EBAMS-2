"""Guard type: Validator.

Guards extension-key resolution: an ``extension_key`` from an enablement row must
map to exactly one registered extension descriptor. An unknown key is a hard error
surfaced at provisioning / CRUD time, never silently skipped.

Also validates that every registered descriptor carries a well-formed
``ExtensionManifest`` (E5). A missing or incomplete manifest is also a hard error.
"""

from __future__ import annotations

import importlib

from app.detail_extensions import registry
from app.detail_extensions.base.extension_descriptor import DetailExtension
from app.detail_extensions.base.manifest import ExtensionManifest


# Keys reserved by the URL router — the panel route uses these as literal segments.
RESERVED_EXTENSION_KEYS: frozenset[str] = frozenset({"asset", "assets", "model", "models", "configuration"})


class UnknownExtensionError(Exception):
    """Raised when an extension_key does not resolve to a registered descriptor."""


class InvalidManifestError(Exception):
    """Raised when a descriptor's manifest is missing or has broken module paths."""


class ReservedKeyError(ValueError):
    """Raised when a descriptor uses a key that collides with a reserved URL segment."""


class ExtensionRegistryValidator:
    """Resolves extension keys to descriptors; validates overall registry integrity."""

    @staticmethod
    def resolve(extension_key: str) -> type[DetailExtension]:
        descriptor = registry.get(extension_key)
        if descriptor is None:
            raise UnknownExtensionError(
                f"Unknown extension_key '{extension_key}'. "
                f"Known keys: {sorted(registry.EXTENSION_REGISTRY)}"
            )
        return descriptor

    @staticmethod
    def assert_registry_valid() -> None:
        """Sanity-check the registry at startup — fails loud on misconfiguration.

        Checks:
        - keys present and unique
        - primary_model declared
        - manifest present and is an ExtensionManifest
        - models_module (if declared) actually imports
        """
        seen: set[str] = set()
        for descriptor in registry.EXTENSION_REGISTRY.values():
            if not descriptor.key:
                raise ValueError(f"Extension {descriptor.__name__} has no key.")
            if descriptor.key in RESERVED_EXTENSION_KEYS:
                raise ReservedKeyError(
                    f"Extension '{descriptor.key}' uses a reserved URL segment. "
                    f"Reserved keys: {sorted(RESERVED_EXTENSION_KEYS)}"
                )
            if descriptor.key in seen:
                raise ValueError(f"Duplicate extension key '{descriptor.key}'.")
            seen.add(descriptor.key)
            if descriptor.primary_model is None:
                raise ValueError(
                    f"Extension '{descriptor.key}' has no primary_model."
                )
            # Manifest validation (E5).
            manifest = descriptor.manifest
            if manifest is None or not isinstance(manifest, ExtensionManifest):
                raise InvalidManifestError(
                    f"Extension '{descriptor.key}' is missing a valid ExtensionManifest. "
                    f"Set the 'manifest' class attribute."
                )
            if manifest.models_module is not None:
                try:
                    importlib.import_module(manifest.models_module)
                except ImportError as exc:
                    raise InvalidManifestError(
                        f"Extension '{descriptor.key}' manifest.models_module "
                        f"'{manifest.models_module}' could not be imported: {exc}"
                    ) from exc
            for dotted_path in manifest.control_modules:
                try:
                    importlib.import_module(dotted_path)
                except ImportError as exc:
                    raise InvalidManifestError(
                        f"Extension '{descriptor.key}' manifest.control_modules "
                        f"entry '{dotted_path}' could not be imported: {exc}"
                    ) from exc
