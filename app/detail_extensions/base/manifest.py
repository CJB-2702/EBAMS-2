"""ExtensionManifest — per-extension file declaration (E5).

A pure declaration struct. Each extension sets one on its descriptor class.
The registry validates that it exists and is well-formed at startup. No logic here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtensionManifest:
    """Enumerates the modules and directories that belong to one extension slice.

    Fields marked ``None`` are reserved for a later phase and skip validation.
    """

    #: Dotted path to the slice's ``models.py`` (required).
    models_module: str | None = None
    #: Dotted paths to the slice's control-layer classes (empty this phase).
    control_modules: list[str] = field(default_factory=list)
    #: Template directory for this extension (reserved, Phase 3).
    template_dir: str | None = None
    #: Entrypoints module (reserved, Phase 3).
    entrypoints_module: str | None = None
    #: URLs module (reserved, Phase 3).
    urls_module: str | None = None
