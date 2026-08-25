"""Adaptor: `RoomSvgAdapter` — sanitization, viewBox normalization, shape-code
extraction, and HTMX attribute injection for both tiers of the SVG spatial
engine (FD-25, FD-29).

One implementation covers both the Room tier (`<g inkscape:label="locations">`
shapes → `RoomLocation.display_code`, exact match) and the RoomLocation tier
(`<g inkscape:label="bins">` shapes → `StorageLocation.atomic_coord`, exact
match) — pass the group label as a parameter rather than duplicating the
parse/inject logic per tier (03a's discrepancy note #4.2: the legacy app had
two independently-drifting parsers; this repo keeps one).

Every uploaded SVG passes through `sanitize()` before anything else touches
it — the sanitized output is the only thing ever stored or rendered with
`|safe`. No shape-matching here is prefix-based (FD-29 supersedes FD-22):
a shape code either exactly matches a target's display code or it doesn't.
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from app.inventory.control_layer.constants import MAX_SVG_UPLOAD_BYTES
from app.inventory.control_layer.errors import SvgUploadError

_DISALLOWED_TAGS = ("script", "foreignObject")
_EXTERNAL_REF_ATTRS = ("href", "xlink:href")

#: Inkscape writes BOTH `xmlns=".../svg"` and `xmlns:svg=".../svg"` on its
#: root element. lxml then re-serializes every element with the `svg:`
#: prefix, and a browser parsing `<svg:svg>` in an HTML document does not
#: resolve it to a real SVG element — the map renders as a flat strip of
#: label text. Since every layout in this feature is Inkscape-authored, the
#: prefix is stripped on the way through.
_SVG_NAMESPACE_PREFIX = "svg"


class RoomSvgAdapter:
    @classmethod
    def read_svg_from_attachment(cls, attachment) -> str | None:
        """Reads raw SVG content from an Attachment model instance, resetting
        the file buffer position to 0 so repeated reads within the same request
        do not return EOF empty bytes."""
        if not attachment or not getattr(attachment, "file", None):
            return None
        try:
            f = attachment.file.file
            f.seek(0)
            content = f.read().decode("utf-8")
            f.seek(0)
            return content
        except Exception:
            return None

    @classmethod
    def check_upload_size(cls, raw_bytes: bytes) -> None:
        if len(raw_bytes) > MAX_SVG_UPLOAD_BYTES:
            raise SvgUploadError(
                [f"SVG upload exceeds the {MAX_SVG_UPLOAD_BYTES // (1024 * 1024)} MB limit."]
            )

    @classmethod
    def sanitize(cls, raw_svg: str) -> str:
        """Strips `<script>`/`<foreignObject>`, every `on*` event-handler
        attribute, and external `href`/`xlink:href` references (anything not
        starting with `#`). Returns the cleaned markup as a string; callers
        must not render anything except this output with `|safe`."""
        soup = BeautifulSoup(raw_svg, "xml")

        for tag_name in _DISALLOWED_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        for tag in soup.find_all(True):
            for attr in list(tag.attrs):
                if attr.lower().startswith("on"):
                    del tag.attrs[attr]
                    continue
                if attr in _EXTERNAL_REF_ATTRS:
                    value = tag.attrs.get(attr, "")
                    if value and not value.startswith("#"):
                        del tag.attrs[attr]

        cls._strip_svg_prefix(soup)
        return str(soup)

    @classmethod
    def _strip_svg_prefix(cls, soup: BeautifulSoup) -> None:
        """Drops the redundant `svg:` prefix (and its now-unused namespace
        declaration) so the serialized markup uses plain `<svg>`/`<rect>`
        tag names an HTML parser understands."""
        for tag in soup.find_all(True):
            if tag.prefix == _SVG_NAMESPACE_PREFIX:
                tag.prefix = None
            if f"xmlns:{_SVG_NAMESPACE_PREFIX}" in tag.attrs:
                del tag.attrs[f"xmlns:{_SVG_NAMESPACE_PREFIX}"]

    @classmethod
    def normalize_viewbox(cls, svg: str) -> str:
        """Ensures a `viewBox` (deriving one from `width`/`height` if
        missing), sets `width=100%`/`height=auto`, and tags the root
        `<svg>` with the `room-svg-canvas` class for responsive scaling."""
        soup = BeautifulSoup(svg, "xml")
        cls._strip_svg_prefix(soup)
        svg_node = soup.find("svg")
        if svg_node is None:
            return svg

        if not svg_node.get("viewBox") and svg_node.get("width") and svg_node.get("height"):
            width = svg_node["width"].replace("px", "")
            height = svg_node["height"].replace("px", "")
            svg_node["viewBox"] = f"0 0 {width} {height}"

        svg_node["width"] = "100%"
        svg_node["height"] = "auto"
        existing_classes = svg_node.get("class", "")
        classes = set(existing_classes.split()) | {"room-svg-canvas"}
        svg_node["class"] = " ".join(sorted(classes))

        return str(soup)

    @classmethod
    def _find_group(cls, soup: BeautifulSoup, *, group_label: str) -> Tag | None:
        return soup.find("g", id=group_label) or soup.find(
            "g", attrs={"inkscape:label": group_label}
        )

    @classmethod
    def extract_shape_codes(cls, svg: str, *, group_label: str) -> list[str]:
        """Shape codes from the named Inkscape layer group's direct
        children — `inkscape:label` preferred, `id` fallback. Order
        preserved, duplicates kept as-is (callers decide how to treat
        collisions)."""
        soup = BeautifulSoup(svg, "xml")
        group = cls._find_group(soup, group_label=group_label)
        if group is None:
            return []

        codes = []
        for element in group.find_all(["rect", "path", "g", "circle", "polygon"], recursive=False):
            code = element.get("inkscape:label") or element.get("id")
            if code:
                codes.append(code)
        return codes

    @classmethod
    def render_interactive_svg(
        cls,
        svg: str,
        *,
        group_label: str,
        shape_targets: dict[str, str],
        canonical_url: str,
        format_param: str,
        drawer_target: str,
    ) -> str:
        """Normalizes the viewBox and injects `hx-get`/`hx-target`/`hx-swap`
        onto every shape whose code exactly matches a key in
        `shape_targets` (FD-17's canonical-URL + `format=` contract — no
        bespoke drawer route). Shapes with no match get a `node-empty` class
        and no interactivity; matched shapes get `node-has-stock` (callers
        needing finer stock-state classing should post-process the string,
        this method only knows matched/unmatched)."""
        normalized = cls.normalize_viewbox(svg)
        soup = BeautifulSoup(normalized, "xml")
        group = cls._find_group(soup, group_label=group_label)
        if group is None:
            return str(soup)

        for element in group.find_all(["rect", "path", "g", "circle", "polygon"], recursive=False):
            code = element.get("inkscape:label") or element.get("id")
            if not code:
                continue

            target_code = shape_targets.get(code)
            classes = ["spatial-node"]
            classes.append("node-has-stock" if target_code is not None else "node-empty")
            element["class"] = " ".join(classes)

            if target_code is not None:
                element["data-loc-code"] = target_code
                if format_param and drawer_target:
                    delimiter = "&" if "?" in canonical_url else "?"
                    element["hx-get"] = f"{canonical_url}{delimiter}format={format_param}&loc={target_code}"
                    element["hx-target"] = f"#{drawer_target}"
                    element["hx-swap"] = "innerHTML"
                    element["hx-trigger"] = "click"
                element["cursor"] = "pointer"

        return str(soup)
