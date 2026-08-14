from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.procurement.control_layer.guards.vendor_uniqueness_guard import (
    VendorValidator,
)
from app.procurement.models import Vendor

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class VendorValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class VendorManager:
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> Vendor:
        errors = VendorValidator.check(name=data.get("name", ""), code=data.get("code"))
        if errors:
            raise VendorValidationError(errors)

        with transaction.atomic():
            vendor = Vendor.objects.create(
                name=data["name"].strip(),
                code=(data.get("code") or None),
                website=(data.get("website") or None),
                is_active=data.get("is_active", True),
                created_by=actor,
                updated_by=actor,
            )
        return vendor
