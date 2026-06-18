"""ExtensionFactory — provisions an extension's row(s) for one owner.

This is the **extension seam**. Today the base creates a single primary-table row.
An extension that needs a multi-table cluster subclasses this and overrides
``provision()`` — the provisioner and descriptor contract are unchanged.

Factories are stateless (class methods only) and run **inside** the outer creation
transaction; they never commit or roll back themselves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.db.models import Model

    from app.detail_extensions.base.extension_descriptor import DetailExtension


class ExtensionFactory:
    """Base provisioning strategy: one primary-table row per owner."""

    @classmethod
    def provision(
        cls,
        *,
        owner: "Model",
        descriptor: "type[DetailExtension]",
        actor: "AbstractUser",
    ) -> "Model":
        """Create and return one primary-table row linking ``owner`` to the extension."""
        owner_field = descriptor.target.owner_field
        return descriptor.primary_model.objects.create(
            **{owner_field: owner},
            created_by=actor,
            updated_by=actor,
        )
