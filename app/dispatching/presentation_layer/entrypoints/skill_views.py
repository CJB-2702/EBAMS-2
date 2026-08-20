"""Skills — catalogue and certification screens (dispatching_starter_kit/
build_phase_3_ui.md §2.1). Editing a catalogue entry is a page, not a modal
(§1.2 — the legacy edit_skill.html modal is DROPped). Certifying a person is
an in-page assignment panel on that person's own certifications page — never
a modal (harness/UX_UI/design_patterns/modals.md)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.dispatching.control_layer.domain_structs.user_skills_struct import UserSkillsStruct
from app.dispatching.control_layer.managers.dispatch_skill_manager import (
    DispatchSkillManager,
    DispatchSkillValidationError,
)
from app.dispatching.control_layer.managers.user_skill_manager import (
    UserSkillManager,
    UserSkillValidationError,
)
from app.dispatching.models.skills.dispatch_skill import DispatchSkill
from app.dispatching.models.skills.user_dispatch_skill import UserDispatchSkill
from app.dispatching.presentation_layer.search.people_search import search_people
from app.dispatching.presentation_layer.search.skill_search import search_skills
from app.dispatching.presentation_layer.tools.dispatching_access import (
    can_certify_skills,
    can_manage_skills_catalogue,
    can_view_skill_catalogue,
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────
# Catalogue
# ─────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def skill_index(request: HttpRequest) -> HttpResponse:
    if not can_view_skill_catalogue(request):
        raise PermissionDenied("Viewing the skills catalogue requires the skills_catalogue or dispatching_read permission.")

    q = request.GET.get("q", "").strip()
    active_filter = request.GET.get("active", "active")
    exclude_certified_for_raw = request.GET.get("exclude_certified_for_user_id", "").strip()
    exclude_certified_for_user_id = (
        int(exclude_certified_for_raw) if exclude_certified_for_raw.isdigit() else None
    )

    skills = search_skills(
        q=q,
        active_only=(active_filter != "all"),
        exclude_certified_for_user_id=exclude_certified_for_user_id,
    )

    if request.GET.get("format") == "htmx-search-results":
        results = [
            f'<li data-value="{s.pk}">{s.name}{" — requires expiry" if s.requires_expiry else ""}</li>'
            for s in skills
        ]
        if not results:
            return HttpResponse('<li class="is-disabled">No matches.</li>')
        return HttpResponse("\n".join(results))

    return render(request, "dispatching/skills/index.html", {
        "skills": skills,
        "q": q,
        "active_filter": active_filter,
        "can_manage": can_manage_skills_catalogue(request),
    })


@require_http_methods(["GET", "POST"])
def skill_create(request: HttpRequest) -> HttpResponse:
    if not can_manage_skills_catalogue(request):
        raise PermissionDenied("Creating a skill requires the skills_catalogue permission.")

    if request.method == "POST":
        data = {
            "name": request.POST.get("name", "").strip(),
            "code": request.POST.get("code", "").strip(),
            "description": request.POST.get("description", "").strip(),
            "requires_expiry": request.POST.get("requires_expiry") == "on",
            "is_active": True,
        }
        try:
            skill = DispatchSkillManager.create(data=data, actor=request.user)
        except DispatchSkillValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(request, "dispatching/skills/form.html", {"skill": None, "form_data": data})

        messages.success(request, f"Skill '{skill.name}' created.")
        return redirect(reverse("dispatching_skill_detail", kwargs={"pk": skill.pk}))

    return render(request, "dispatching/skills/form.html", {"skill": None, "form_data": {}})


@require_http_methods(["GET"])
def skill_detail(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_view_skill_catalogue(request):
        raise PermissionDenied("Viewing a skill requires the skills_catalogue or dispatching_read permission.")

    skill = get_object_or_404(DispatchSkill, pk=pk)
    certifications = list(
        UserDispatchSkill.objects.filter(skill=skill, is_active=True)
        .select_related("user")
        .order_by("user__username")
    )

    from app.dispatching.models.templates.template_requested_skill import (
        DispatchTemplateRequestedSkill,
    )

    # skill's FK on this table is related_name="+" (no reverse accessor) —
    # query it directly, and keep only rows on the CURRENT head revision.
    required_by_templates = [
        r
        for r in DispatchTemplateRequestedSkill.objects.filter(skill=skill)
        .select_related("revision", "revision__template")
        if r.revision_id == r.revision.template.head_revision_id
    ]

    return render(request, "dispatching/skills/detail.html", {
        "skill": skill,
        "certifications": certifications,
        "required_by_templates": required_by_templates,
        "can_manage": can_manage_skills_catalogue(request),
    })


@require_http_methods(["GET", "POST"])
def skill_edit(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_manage_skills_catalogue(request):
        raise PermissionDenied("Editing a skill requires the skills_catalogue permission.")

    skill = get_object_or_404(DispatchSkill, pk=pk)

    if request.method == "POST":
        data = {
            "name": request.POST.get("name", "").strip(),
            "code": request.POST.get("code", "").strip(),
            "description": request.POST.get("description", "").strip(),
            "requires_expiry": request.POST.get("requires_expiry") == "on",
        }
        try:
            skill = DispatchSkillManager.update(skill_id=pk, data=data, actor=request.user)
        except DispatchSkillValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(request, "dispatching/skills/form.html", {"skill": skill, "form_data": data})

        messages.success(request, f"Skill '{skill.name}' updated.")
        return redirect(reverse("dispatching_skill_detail", kwargs={"pk": skill.pk}))

    return render(request, "dispatching/skills/form.html", {"skill": skill, "form_data": None})


@require_http_methods(["POST"])
def skill_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_manage_skills_catalogue(request):
        raise PermissionDenied("Activating or deactivating a skill requires the skills_catalogue permission.")

    skill = get_object_or_404(DispatchSkill, pk=pk)
    if skill.is_active:
        DispatchSkillManager.deactivate(skill_id=pk, actor=request.user)
        messages.success(request, f"'{skill.name}' deactivated.")
    else:
        DispatchSkillManager.reactivate(skill_id=pk, actor=request.user)
        messages.success(request, f"'{skill.name}' reactivated.")
    return redirect(reverse("dispatching_skill_detail", kwargs={"pk": pk}))


# ─────────────────────────────────────────────────────────────────────────
# Linkage portal — browse people to reach their certifications
# ─────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def skills_linkage_portal(request: HttpRequest) -> HttpResponse:
    if not can_certify_skills(request):
        raise PermissionDenied("Browsing certifications by person requires the skills_certify permission.")

    q = request.GET.get("q", "").strip()
    cert_name = request.GET.get("cert_name", "").strip()
    people = search_people(q=q, cert_name=cert_name)

    if request.GET.get("format") == "htmx-search-results":
        return render(request, "dispatching/skills/_linkage_results.html", {"people": people})

    return render(request, "dispatching/skills/linkage_portal.html", {"people": people, "q": q, "cert_name": cert_name})


# ─────────────────────────────────────────────────────────────────────────
# A person's certifications — assignment panel plus "my own certifications"
# ─────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def user_skills(request: HttpRequest, user_id: int) -> HttpResponse:
    """One canonical URL serves both "a person's certifications" (Skills —
    Certify) and "my own certifications" (everyone, read-only) —
    5_roles_and_permissions.md §4.4."""
    is_self = user_id == request.user.pk
    if not is_self and not can_certify_skills(request):
        raise PermissionDenied("Viewing another person's certifications requires the skills_certify permission.")

    target = get_object_or_404(User, pk=user_id)
    struct = UserSkillsStruct.load(user_id=user_id)

    from django.utils import timezone

    return render(request, "dispatching/skills/user_skills.html", {
        "target": target,
        "is_self": is_self,
        "certifications": struct.certifications,
        "can_certify": can_certify_skills(request),
        "today": timezone.now().date(),
    })


@require_http_methods(["GET"])
def my_certifications(request: HttpRequest) -> HttpResponse:
    return redirect(reverse("dispatching_user_skills", kwargs={"user_id": request.user.pk}))


@require_http_methods(["POST"])
def certification_certify(request: HttpRequest, user_id: int) -> HttpResponse:
    if not can_certify_skills(request):
        raise PermissionDenied("Certifying a person requires the skills_certify permission.")
    get_object_or_404(User, pk=user_id)

    level_raw = request.POST.get("level", "").strip()
    data = {
        "user_id": user_id,
        "skill_id": int(request.POST.get("skill_id", 0) or 0),
        "level": int(level_raw) if level_raw.isdigit() else None,
        "certified_at": request.POST.get("certified_at") or None,
        "expires_at": request.POST.get("expires_at") or None,
        "certificate_number": request.POST.get("certificate_number", "").strip(),
    }
    try:
        UserSkillManager.certify(data=data, actor=request.user)
        messages.success(request, "Certification recorded.")
    except UserSkillValidationError as exc:
        for error in exc.errors:
            messages.error(request, error)

    return redirect(reverse("dispatching_user_skills", kwargs={"user_id": user_id}))


@require_http_methods(["POST"])
def certification_update(request: HttpRequest, pk: int) -> HttpResponse:
    certification = get_object_or_404(UserDispatchSkill, pk=pk)
    if not can_certify_skills(request):
        raise PermissionDenied("Editing a certification requires the skills_certify permission.")

    level_raw = request.POST.get("level", "").strip()
    data = {
        "level": int(level_raw) if level_raw.isdigit() else None,
        "certified_at": request.POST.get("certified_at") or None,
        "expires_at": request.POST.get("expires_at") or None,
        "certificate_number": request.POST.get("certificate_number", "").strip(),
    }
    try:
        UserSkillManager.update(user_skill_id=pk, data=data, actor=request.user)
        messages.success(request, "Certification updated.")
    except UserSkillValidationError as exc:
        for error in exc.errors:
            messages.error(request, error)

    return redirect(reverse("dispatching_user_skills", kwargs={"user_id": certification.user_id}))


@require_http_methods(["POST"])
def certification_revoke(request: HttpRequest, pk: int) -> HttpResponse:
    certification = get_object_or_404(UserDispatchSkill, pk=pk)
    if not can_certify_skills(request):
        raise PermissionDenied("Revoking a certification requires the skills_certify permission.")

    UserSkillManager.revoke(user_skill_id=pk, actor=request.user)
    messages.success(request, "Certification revoked.")
    return redirect(reverse("dispatching_user_skills", kwargs={"user_id": certification.user_id}))
