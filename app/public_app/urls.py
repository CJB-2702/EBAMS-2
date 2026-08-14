from django.urls import path

from app.public_app.presentation_layer.entrypoints.about import public_about
from app.public_app.presentation_layer.entrypoints.docs.administration import (
    docs_administration_data_domains,
    docs_administration_domain_templates,
    docs_administration_overview,
    docs_administration_roles,
)
from app.public_app.presentation_layer.entrypoints.features import public_features
from app.public_app.presentation_layer.entrypoints.get_started import public_get_started
from app.public_app.presentation_layer.entrypoints.home import public_home
from app.public_app.presentation_layer.entrypoints.learn_more import public_learn_more
from app.public_app.presentation_layer.entrypoints.pricing import public_pricing
from app.public_app.presentation_layer.entrypoints.kitchen_sink import (
    kitchen_sink,
    kitchen_sink_cards,
    kitchen_sink_dp_detail,
    kitchen_sink_dp_index,
    kitchen_sink_dummy_htmx_fragment,
    kitchen_sink_dummy_list_rows,
    kitchen_sink_dummy_search_results,
    kitchen_sink_dummy_supplier_item_search,
    kitchen_sink_wc_detail,
    kitchen_sink_wc_index,
)
from app.public_app.presentation_layer.entrypoints.logout import PublicLogoutView

urlpatterns = [
    path("", public_home, name="public_home"),
    path("about/", public_about, name="public_about"),
    path("site/about/", public_about, name="public_about_site_path"),
    path("features/", public_features, name="public_features"),
    path("get-started/", public_get_started, name="public_get_started"),
    path("learn-more/", public_learn_more, name="public_learn_more"),
    path("pricing/", public_pricing, name="public_pricing"),
    path(
        "logout/",
        PublicLogoutView.as_view(),
        name="public_logout",
    ),
    path("docs/administration/", docs_administration_overview, name="docs_administration_overview"),
    path("docs/administration/roles/", docs_administration_roles, name="docs_administration_roles"),
    path("docs/administration/data-domains/", docs_administration_data_domains, name="docs_administration_data_domains"),
    path("docs/administration/domain-templates/", docs_administration_domain_templates, name="docs_administration_domain_templates"),
    path("kitchen-sink/", kitchen_sink, name="kitchen_sink"),
    path("kitchen-sink/cards/", kitchen_sink_cards, name="kitchen_sink_cards"),
    path("kitchen-sink/dummy-data/search-results", kitchen_sink_dummy_search_results, name="kitchen_sink_dummy_search_results"),
    path("kitchen-sink/dummy-data/list-rows", kitchen_sink_dummy_list_rows, name="kitchen_sink_dummy_list_rows"),
    path("kitchen-sink/dummy-data/htmx-fragment", kitchen_sink_dummy_htmx_fragment, name="kitchen_sink_dummy_htmx_fragment"),
    path("kitchen-sink/dummy-data/supplier-item-search", kitchen_sink_dummy_supplier_item_search, name="kitchen_sink_dummy_supplier_item_search"),
    path("kitchen-sink/web-components/", kitchen_sink_wc_index, name="kitchen_sink_wc_index"),
    path("kitchen-sink/web-components/<slug:component_name>/", kitchen_sink_wc_detail, name="kitchen_sink_wc_detail"),
    path("kitchen-sink/design-patterns/", kitchen_sink_dp_index, name="kitchen_sink_dp_index"),
    path("kitchen-sink/design-patterns/<slug:pattern_name>/", kitchen_sink_dp_detail, name="kitchen_sink_dp_detail"),
]
