"""PartCreationWizardFactory — composes the existing single-model factories/managers
into the /parts/new/ wizard's one-shot creation: identity + optional domain scoping +
zero-or-more manufacturer/supplier-item pairs, in one transaction."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.parts.control_layer.errors import PartValidationError
from app.parts.control_layer.factories.part_factory import PartFactory
from app.parts.control_layer.handlers.part_domain_template_handler import (
    PartDomainTemplateHandler,
)
from app.parts.control_layer.managers.part_domain_manager import PartDomainManager
from app.parts.control_layer.managers.supplier_item_manager import SupplierItemManager
from app.parts.models import Part

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class PartCreationWizardFactory:
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> Part:
        # A part is never "simple" (D-something) without at least one manufacturer /
        # supplier item — enforced here rather than in PartValidator since it's a
        # wizard-level (cross-aggregate) rule, not a Part-identity rule.
        if not data["supplier_items"]:
            raise PartValidationError(
                ["At least one manufacturer / supplier item is required."]
            )

        with transaction.atomic():
            part = PartFactory.create(data=data["identity"], actor=actor)

            domains = data["domains"]
            if domains["template_id"]:
                PartDomainTemplateHandler(part, actor).apply(domains["template_id"])
            for domain_id in domains["domain_ids"]:
                PartDomainManager(part, actor).add_domain(domain_id)

            for row in data["supplier_items"]:
                SupplierItemManager.create(
                    actor=actor, data={**row, "internal_part_id": part.id}
                )
                # SupplierItemManager.create already recomputes
                # Part.primary_manufacturer / primary_supplier_item / is_simple_part.

        return part
