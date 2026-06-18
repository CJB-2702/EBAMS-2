from __future__ import annotations

import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models

from app.administration.models.auth.domains_mixin import DomainsMixin


class User(AbstractUser, DomainsMixin):
    """
    Custom user model. Extends AbstractUser with a random URL-safe slug.
    Set AUTH_USER_MODEL = "administration.User" in settings.
    """

    slug = models.CharField(max_length=8, unique=True, editable=False)

    class Meta:
        db_table = "administration_user"

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    @staticmethod
    def _unique_slug() -> str:
        slug = secrets.token_urlsafe(6)
        while User.objects.filter(slug=slug).exists():
            slug = secrets.token_urlsafe(6)
        return slug

    def __str__(self) -> str:
        return self.username
