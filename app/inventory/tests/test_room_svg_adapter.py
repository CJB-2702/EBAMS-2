"""Tests for `RoomSvgAdapter`: sanitization, viewBox normalization, exact
shape-code extraction, and HTMX attribute injection (FD-25/FD-29).
"""

from __future__ import annotations

from django.test import SimpleTestCase

from app.inventory.control_layer.adapters.room_svg_adapter import RoomSvgAdapter
from app.inventory.control_layer.errors import SvgUploadError

MALICIOUS_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <script>alert('xss')</script>
  <foreignObject><div>evil</div></foreignObject>
  <g id="locations">
    <rect id="0005-0002" onclick="alert(1)" href="http://evil.example/x" />
    <rect inkscape:label="0001-0001" xlink:href="http://evil.example/y" />
  </g>
</svg>"""

CLEAN_ROOM_SVG = """<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" viewBox="0 0 200 200">
  <g inkscape:label="locations">
    <rect inkscape:label="0005-0002" x="0" y="0" width="10" height="10" />
    <rect inkscape:label="0001-0001" x="20" y="20" width="10" height="10" />
    <rect id="0009-0009" x="40" y="40" width="10" height="10" />
  </g>
</svg>"""


class SanitizeTests(SimpleTestCase):
    def test_strips_script_tag(self):
        cleaned = RoomSvgAdapter.sanitize(MALICIOUS_SVG)
        self.assertNotIn("<script", cleaned)
        self.assertNotIn("alert('xss')", cleaned)

    def test_strips_foreign_object(self):
        cleaned = RoomSvgAdapter.sanitize(MALICIOUS_SVG)
        self.assertNotIn("foreignObject", cleaned)

    def test_strips_event_handler_attributes(self):
        cleaned = RoomSvgAdapter.sanitize(MALICIOUS_SVG)
        self.assertNotIn("onclick", cleaned)

    def test_strips_external_href_references(self):
        cleaned = RoomSvgAdapter.sanitize(MALICIOUS_SVG)
        self.assertNotIn("evil.example", cleaned)

    def test_clean_svg_passes_through_with_shapes_intact(self):
        cleaned = RoomSvgAdapter.sanitize(CLEAN_ROOM_SVG)
        self.assertIn("0005-0002", cleaned)
        self.assertIn("0001-0001", cleaned)

    def test_oversized_upload_is_rejected(self):
        with self.assertRaises(SvgUploadError):
            RoomSvgAdapter.check_upload_size(b"x" * (2 * 1024 * 1024 + 1))

    def test_upload_at_limit_is_accepted(self):
        RoomSvgAdapter.check_upload_size(b"x" * (2 * 1024 * 1024))


class ViewboxNormalizationTests(SimpleTestCase):
    def test_missing_viewbox_derived_from_width_height(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="300px" height="150px"></svg>'
        normalized = RoomSvgAdapter.normalize_viewbox(svg)
        self.assertIn('viewBox="0 0 300 150"', normalized)

    def test_width_and_class_are_set_for_responsive_scaling(self):
        normalized = RoomSvgAdapter.normalize_viewbox(CLEAN_ROOM_SVG)
        self.assertIn('width="100%"', normalized)
        self.assertIn("room-svg-canvas", normalized)


class ExtractShapeCodesTests(SimpleTestCase):
    def test_extracts_inkscape_label_preferring_over_id(self):
        codes = RoomSvgAdapter.extract_shape_codes(CLEAN_ROOM_SVG, group_label="locations")
        self.assertEqual(codes, ["0005-0002", "0001-0001", "0009-0009"])

    def test_missing_group_returns_empty_list(self):
        codes = RoomSvgAdapter.extract_shape_codes(CLEAN_ROOM_SVG, group_label="bins")
        self.assertEqual(codes, [])


class RenderInteractiveSvgTests(SimpleTestCase):
    def test_matched_shape_gets_htmx_attributes(self):
        rendered = RoomSvgAdapter.render_interactive_svg(
            CLEAN_ROOM_SVG,
            group_label="locations",
            shape_targets={"0005-0002": "0005-0002"},
            canonical_url="/inventory/room/1",
            format_param="htmx-location-drawer",
            drawer_target="location-detail-drawer",
        )
        # BeautifulSoup's XML serializer escapes `&` as `&amp;` in attribute
        # values (required for well-formed XML; browsers/HTMX decode it back).
        self.assertIn(
            'hx-get="/inventory/room/1?format=htmx-location-drawer&amp;loc=0005-0002"',
            rendered,
        )
        self.assertIn('hx-target="#location-detail-drawer"', rendered)
        self.assertIn("node-has-stock", rendered)

    def test_unmatched_shape_gets_no_htmx_attributes(self):
        rendered = RoomSvgAdapter.render_interactive_svg(
            CLEAN_ROOM_SVG,
            group_label="locations",
            shape_targets={"0005-0002": "0005-0002"},
            canonical_url="/inventory/room/1",
            format_param="htmx-location-drawer",
            drawer_target="location-detail-drawer",
        )
        self.assertIn("node-empty", rendered)
        self.assertNotIn('inkscape:label="0001-0001"><rect', rendered)  # sanity: still parseable

    def test_no_prefix_matching_only_exact(self):
        """FD-29 supersedes FD-22's prefix-match: a shape code that is only a
        prefix of a target must not be treated as matched."""
        rendered = RoomSvgAdapter.render_interactive_svg(
            CLEAN_ROOM_SVG,
            group_label="locations",
            shape_targets={"0005": "0005"},
            canonical_url="/inventory/room/1",
            format_param="htmx-location-drawer",
            drawer_target="location-detail-drawer",
        )
        # "0005-0002" is not an exact match for target key "0005"
        self.assertNotIn("loc=0005-0002", rendered)

    def test_canonical_url_with_existing_query_params(self):
        rendered = RoomSvgAdapter.render_interactive_svg(
            CLEAN_ROOM_SVG,
            group_label="locations",
            shape_targets={"0005-0002": "0005-0002"},
            canonical_url="/inventory/movements/create/?stock=9&warehouse_id=1&room_id=8",
            format_param="htmx-putaway-target",
            drawer_target="destination-target",
        )
        self.assertIn(
            'hx-get="/inventory/movements/create/?stock=9&amp;warehouse_id=1&amp;room_id=8&amp;format=htmx-putaway-target&amp;loc=0005-0002"',
            rendered,
        )
