from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, HttpResponse, Http404
from django.shortcuts import render

_PERMISSIONS = [
    {"id": 1, "label": "read_asset", "description": "Can read assets"},
    {"id": 2, "label": "write_asset", "description": "Can write assets"},
    {"id": 3, "label": "delete_asset", "description": "Can delete assets"},
    {"id": 4, "label": "manage_users", "description": "Can manage users"},
    {"id": 5, "label": "view_reports", "description": "Can view reports"},
    {"id": 6, "label": "export_data", "description": "Can export data"},
    {"id": 7, "label": "import_data", "description": "Can import data"},
    {"id": 8, "label": "admin_panel", "description": "Can access admin panel"},
]

_ASSETS = [
    {"id": 1, "name": "Asset Alpha", "status": "active", "owner": "alice", "domain": "Operations"},
    {"id": 2, "name": "Asset Beta", "status": "inactive", "owner": "bob", "domain": "Finance"},
    {"id": 3, "name": "Asset Gamma", "status": "active", "owner": "carol", "domain": "Operations"},
    {"id": 4, "name": "Asset Delta", "status": "pending", "owner": "dave", "domain": "HR"},
    {"id": 5, "name": "Widget Prime", "status": "active", "owner": "eve", "domain": "Finance"},
]


@login_not_required
def kitchen_sink(request: HttpRequest) -> HttpResponse:
    return render(request, "kitchen_sink/index.html")


@login_not_required
def kitchen_sink_dummy_search_results(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").lower()
    items = _PERMISSIONS
    if q:
        items = [i for i in items if q in i["label"] or q in i["description"]]
    return render(request, "kitchen_sink/fragments/search_results.html", {"items": items})


@login_not_required
def kitchen_sink_dummy_list_rows(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").lower()
    rows = _ASSETS
    if q:
        rows = [r for r in rows if q in r["name"].lower() or q in r["owner"].lower() or q in r["domain"].lower()]
    return render(request, "kitchen_sink/fragments/list_rows.html", {"rows": rows})


@login_not_required
def kitchen_sink_dummy_htmx_fragment(request: HttpRequest) -> HttpResponse:
    return render(request, "kitchen_sink/fragments/htmx_fragment.html")


@login_not_required
def kitchen_sink_work_portal_example(request: HttpRequest) -> HttpResponse:
    return render(request, "kitchen_sink/structural_examples/work_portal.html")


@login_not_required
def kitchen_sink_search_page_example(request: HttpRequest) -> HttpResponse:
    return render(request, "kitchen_sink/structural_examples/search_page.html")


@login_not_required
def kitchen_sink_index_example(request: HttpRequest) -> HttpResponse:
    return render(request, "kitchen_sink/structural_examples/portal_index.html")


@login_not_required
def kitchen_sink_sidebar_behavior_example(request: HttpRequest) -> HttpResponse:
    return render(request, "kitchen_sink/structural_examples/sidebar_behavior.html")


@login_not_required
def kitchen_sink_topbar_popovers(request: HttpRequest) -> HttpResponse:
    return render(request, "kitchen_sink/structural_examples/top_bar_behavior/popovers.html")


@login_not_required
def kitchen_sink_wc_index(request: HttpRequest) -> HttpResponse:
    return render(request, "kitchen_sink/web_components/index.html")


@login_not_required
def kitchen_sink_wc_detail(request: HttpRequest, component_name: str) -> HttpResponse:
    valid_components = {
        "collapsable-side-bar",
        "dual-listbox",
        "image-carousel",
        "list-box",
        "search-dropdown",
        "toast-alert",
    }
    if component_name not in valid_components:
        raise Http404("Web Component not found")
    template_name = f"kitchen_sink/web_components/{component_name.replace('-', '_')}.html"
    return render(request, template_name, {"current_component": component_name})
