"""Guard type: Validator. Vendor name/code uniqueness."""

from __future__ import annotations

from app.procurement.models import Vendor


class VendorValidator:
    @classmethod
    def check(
        cls, *, name: str, code: str | None, exclude_vendor_id: int | None = None
    ) -> list[str]:
        errors: list[str] = []
        name = (name or "").strip()
        if not name:
            errors.append("Vendor name is required.")

        qs = Vendor.objects.filter(name=name)
        if exclude_vendor_id is not None:
            qs = qs.exclude(id=exclude_vendor_id)
        if name and qs.exists():
            errors.append(f"A vendor with name '{name}' already exists.")

        if code:
            qs = Vendor.objects.filter(code=code)
            if exclude_vendor_id is not None:
                qs = qs.exclude(id=exclude_vendor_id)
            if qs.exists():
                errors.append(f"A vendor with code '{code}' already exists.")

        return errors
