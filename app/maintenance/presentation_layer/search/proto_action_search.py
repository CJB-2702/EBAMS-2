"""Search: domain-scoped pool queries for the Proto Action Library, used by
the template builder's "Add step" card.

Legacy: proto_index's own inline filtering, extended here with the
"used on model" join the builder's pool needs (a ProtoActionItem carries no
asset-model field of its own — the only way to know a library action applies
to a given model is through the TemplateActionItems that were built from it).
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem
from app.maintenance.models.templates.template_action_item import TemplateActionItem


class ProtoActionSearch:
    @classmethod
    def library_pool(
        cls,
        *,
        domain_ids,
        q: str = "",
        used_on_model_id: int | None = None,
    ) -> QuerySet[ProtoActionItem]:
        qs = ProtoActionItem.objects.filter(
            domain_id__in=domain_ids, deleted_at__isnull=True
        ).select_related("domain")

        if q:
            qs = qs.filter(Q(action_name__icontains=q) | Q(description__icontains=q))

        if used_on_model_id:
            # Join through the TemplateActionItems actually built from each
            # proto row to the asset models their own template is scoped to.
            proto_ids = TemplateActionItem.objects.filter(
                template_action_set__asset_models__id=used_on_model_id,
                proto_action_item_id__isnull=False,
                deleted_at__isnull=True,
            ).values_list("proto_action_item_id", flat=True)
            qs = qs.filter(pk__in=proto_ids)

        return qs.order_by("action_name")
