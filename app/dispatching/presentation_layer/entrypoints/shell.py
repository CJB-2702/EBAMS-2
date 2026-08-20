"""Dispatching application shell: hub and entry point.

Pass 1 (build_phase_3_ui.md §2.4) — links to Templates and Skills; the
dispatcher queue and dispatch create/edit are pass 2 and render disabled,
not as broken links."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.dispatching.models.skills.dispatch_skill import DispatchSkill
from app.dispatching.presentation_layer.tools.dispatching_access import (
    accessible_domain_ids,
    can_author_templates,
    can_manage_skills_catalogue,
    can_read_dispatching,
)


@require_http_methods(["GET"])
def dispatching_hub(request: HttpRequest) -> HttpResponse:
    """Dispatching hub — entry point for the dispatching application."""
    from app.dispatching.models.templates.dispatch_template import DispatchTemplate

    domain_ids = accessible_domain_ids(request)
    return render(request, "dispatching/hub.html", {
        "template_count": DispatchTemplate.objects.filter(
            domain_id__in=domain_ids, is_retired=False
        ).count(),
        "skill_count": DispatchSkill.objects.filter(is_active=True).count(),
        "can_author_templates": can_author_templates(request),
        "can_manage_skills": can_manage_skills_catalogue(request) or can_read_dispatching(request),
    })
