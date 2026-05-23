from django.urls import path

from app.public_app.presentation_layer.entrypoints.about import public_about
from app.public_app.presentation_layer.entrypoints.docs.administration import (
    docs_administration_data_domains,
    docs_administration_domain_templates,
    docs_administration_overview,
    docs_administration_roles,
)
from app.public_app.presentation_layer.entrypoints.home import public_home
from app.public_app.presentation_layer.entrypoints.kitchen_sink import (
    kitchen_sink,
    kitchen_sink_dummy_htmx_fragment,
    kitchen_sink_dummy_list_rows,
    kitchen_sink_dummy_search_results,
    kitchen_sink_index_example,
    kitchen_sink_search_page_example,
    kitchen_sink_sidebar_behavior_example,
    kitchen_sink_topbar_popovers,
    kitchen_sink_wc_detail,
    kitchen_sink_wc_index,
    kitchen_sink_work_portal_example,
)
from app.public_app.presentation_layer.entrypoints.logout import PublicLogoutView

urlpatterns = [
    path("", public_home, name="public_home"),
    path("about/", public_about, name="public_about"),
    path("site/about/", public_about, name="public_about_site_path"),
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
    path("kitchen-sink/dummy-data/search-results", kitchen_sink_dummy_search_results, name="kitchen_sink_dummy_search_results"),
    path("kitchen-sink/dummy-data/list-rows", kitchen_sink_dummy_list_rows, name="kitchen_sink_dummy_list_rows"),
    path("kitchen-sink/dummy-data/htmx-fragment", kitchen_sink_dummy_htmx_fragment, name="kitchen_sink_dummy_htmx_fragment"),
    path("kitchen-sink/work-portal-example", kitchen_sink_work_portal_example, name="kitchen_sink_work_portal_example"),
    path("kitchen-sink/search-page-example", kitchen_sink_search_page_example, name="kitchen_sink_search_page_example"),
    path("kitchen-sink/index-example", kitchen_sink_index_example, name="kitchen_sink_index_example"),
    path("kitchen-sink/sidebar-behavior", kitchen_sink_sidebar_behavior_example, name="kitchen_sink_sidebar_behavior_example"),
    path("kitchen-sink/top-bar-behavior/popovers.html", kitchen_sink_topbar_popovers, name="kitchen_sink_topbar_popovers"),
    path("kitchen-sink/web-components/", kitchen_sink_wc_index, name="kitchen_sink_wc_index"),
    path("kitchen-sink/<slug:component_name>/", kitchen_sink_wc_detail, name="kitchen_sink_wc_detail"),
]
