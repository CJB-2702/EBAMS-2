"""Adaptors mapping configuration HTTP POST payloads to structured write input.

All boundary coercion lives here: ``getlist`` for the dual-listbox sets,
checkbox→bool, blank→None, ids→int. Field names follow the actual template
``name=`` attributes (e.g. the form posts ``model`` / ``modifications`` /
``classes`` / ``template``).
"""

from __future__ import annotations

from app.assets.models.configurations import VerificationStatus


class DefinedModificationCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "name": (post.get("name") or "").strip(),
            "code": (post.get("code") or "").strip().upper(),
            "category": (post.get("category") or "").strip() or None,
            "description": (post.get("description") or "").strip() or None,
            "is_active": _checkbox(post, "is_active"),
        }


class DefinedModificationEditAdaptor:
    """Edit posts the same fields; ``code`` is readonly so it is unchanged."""

    @staticmethod
    def from_post(post) -> dict:
        return DefinedModificationCreateAdaptor.from_post(post)


class ConfigurationTemplateCreateAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        return {
            "name": (post.get("name") or "").strip(),
            "revision": (post.get("revision") or "").strip() or None,
            "description": (post.get("description") or "").strip() or None,
            "model_id": _to_int(post.get("model")),
            "modification_ids": _int_list(post, "modifications"),
        }


class ConfigurationTemplateEditAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        data = ConfigurationTemplateCreateAdaptor.from_post(post)
        data["is_active"] = _checkbox(post, "is_active")
        return data


class ApplicabilityEditAdaptor:
    """The dual-listboxes post the desired full class / model sets."""

    @staticmethod
    def from_post(post) -> dict:
        return {
            "class_ids": _int_list(post, "classes"),
            "model_ids": _int_list(post, "models"),
        }


_VERIFICATION_ALIASES = {"verified": VerificationStatus.COMPLETE.value}


class AssetConfigurationEditAdaptor:
    @staticmethod
    def from_post(post) -> dict:
        raw_status = (post.get("verification_status") or "").strip()
        status = _VERIFICATION_ALIASES.get(raw_status, raw_status) or None
        return {
            "template_id": _to_int(post.get("template")),
            "verification_status": status,
            "notes": (post.get("notes") or "").strip() or None,
            "modification_ids": _int_list(post, "modifications"),
        }


def _checkbox(post, key: str) -> bool:
    return post.get(key) in ("on", "true", "True", "1")


def _to_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_list(post, key: str) -> list[int]:
    out: list[int] = []
    for raw in post.getlist(key):
        try:
            out.append(int(raw))
        except (TypeError, ValueError):
            continue
    return out
