from __future__ import annotations

from collections.abc import Iterable

from django.db import models


class DomainsMixin(models.Model):
    """Domain-scope methods on the user, mirroring PermissionsMixin.

    Active UserDomain rows are the flattened source of truth: domain templates
    are materialized into UserDomain rows by TemplateDomainRebaseHandler, so
    there is no separate "group" source to union at check time (unlike Django
    group permissions). The cache lives on the in-memory user instance for the
    request lifetime, like Django's _perm_cache.
    """

    class Meta:
        abstract = True

    def _load_domain_cache(self) -> None:
        if hasattr(self, "_domain_id_cache"):
            return
        from app.administration.models.data_ownership.domains import Domain

        rows = list(
            Domain.objects.filter(
                user_domain_links__user=self,
                user_domain_links__is_active=True,
            )
            .values("id", "slug")
            .distinct()
        )
        self._domain_id_cache = frozenset(r["id"] for r in rows)
        self._domain_slug_cache = frozenset(r["slug"] for r in rows)

    def get_all_domains(self) -> frozenset[str]:
        """Return the slugs of every active domain assigned to this user."""
        if not self.is_active:
            return frozenset()
        self._load_domain_cache()
        return self._domain_slug_cache

    def get_all_domain_ids(self) -> frozenset[int]:
        """Return the primary keys of every active domain assigned to this user."""
        if not self.is_active:
            return frozenset()
        self._load_domain_cache()
        return self._domain_id_cache

    def has_domain(self, slug: str) -> bool:
        """Return True if the user has access to the domain with this slug."""
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        return slug in self.get_all_domains()

    def has_domains(self, slugs: Iterable[str]) -> bool:
        """Return True if the user has access to every domain slug given."""
        if isinstance(slugs, str):
            raise ValueError("slugs must be an iterable of slugs, not a str.")
        return all(self.has_domain(s) for s in slugs)
