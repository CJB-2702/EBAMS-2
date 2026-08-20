"""Read helper for the skills linkage portal — browsing/searching people to
open their certification page (dispatching_starter_kit/application_map.md
§2, legacy linkage_portal.html)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, QuerySet

User = get_user_model()


def search_people(*, q: str = "", cert_name: str = "") -> QuerySet:
    qs = User.objects.filter(is_active=True)

    q = (q or "").strip()
    if q:
        qs = qs.filter(username__icontains=q)

    cert_name = (cert_name or "").strip()
    if cert_name:
        qs = qs.filter(dispatch_skills__skill__name__icontains=cert_name, dispatch_skills__is_active=True).distinct()

    qs = qs.annotate(cert_count=Count("dispatch_skills", filter=Q(dispatch_skills__is_active=True))).order_by("username")
    return qs
