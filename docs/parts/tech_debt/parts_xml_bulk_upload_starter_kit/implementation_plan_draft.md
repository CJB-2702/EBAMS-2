# Implementation Plan Draft — XML Bulk Parts Ingest

**Status:** deferred, not built. Drafted 2026-08-08 in the same session that started this kit's questionnaire, then set aside before implementation. Kept here as a running-start for whoever picks this back up — it resolves several of the questionnaire's open questions (R1, R2 partially, M1's suffix question, M3's explicit-vs-inferred question) by picking concrete answers rather than leaving them open. Those picks should be re-confirmed against `questionnaire.md`/`initial_prompt.md` before building, not assumed still correct.

## Context

The Parts app already has a paste-from-Excel bulk-upload flow (`/parts/bulk-upload/`) but it's flat: one row = one part with exactly one manufacturer/supplier item, no aliases, no domain scoping. The goal here is a second bulk-import path, from an uploaded **XML file**, that supports a richer nested shape: a `<part>` can carry multiple `<supplier-item>` blocks (each with its own `<manufacturer>`), a list of `<additional-aliases>`, and a list of `<assigned-domains>`. This needs a new page at `/parts/bulk-upload/xml/` that documents the expected structure, offers an XSD download, accepts an upload, and reports per-part success/failure back to the user — mirroring the UX of the existing bulk-upload results table.

## XML structure (final)

```xml
<partset>
  <part part_number="PN-10023" name="M3x8 Socket Head Cap Screw"
        part_type="fastener" category="hardware" is_active="true">
    <description>Stainless steel, DIN 912</description>

    <supplier-item manufacturer_part_number="SHC-M3-8-SS" name="M3x8 SHCS Stainless" is_active="true">
      <description>Vendor-packaged qty 100</description>
      <manufacturer name="Fastenal" code="FSTL" website="https://www.fastenal.com" />
    </supplier-item>

    <additional-aliases>
      <alias type="LEGACY">M3-8-SHCS</alias>
      <alias>SCREW-M3X8-SS</alias>  <!-- type optional, defaults to IMPORTED -->
    </additional-aliases>

    <assigned-domains>
      <domain slug="west-region" title="West Region" />
    </assigned-domains>
  </part>
</partset>
```

- `<part>` required attrs: `part_number`, `name`. Optional: `part_type`, `category`, `is_active` (default true).
- `<supplier-item>` (0+ per part) required attr: `manufacturer_part_number`. Optional: `name`, `is_active`. Required child: `<manufacturer name="...">` (optional `code`, `website`).
- `<additional-aliases><alias type="...">value</alias></additional-aliases>` — `type` optional, defaults to `IMPORTED`.
- `<assigned-domains><domain slug="..." title="..."/></assigned-domains>` — resolved by `slug` only (must already exist — **hard error** if not found, not a get-or-create, since `Domain` is an administration-owned RBAC primitive). `title` is informational only; a mismatch against the resolved domain's `name` is not cross-checked.
- **Failure scope (confirmed with developer during drafting): whole-`<part>` rollback.** If any child (supplier-item/manufacturer/alias/domain) fails, the entire `<part>` is rolled back and reported as one failed row with all collected error messages — same all-or-nothing semantics as `PartCreationWizardFactory`. No partial parts.
- **Not addressed by this draft:** the questionnaire's `PART_TO_PART` alternate-part alias / forward-reference question (R1, M5) — this draft's `<additional-aliases>` only covers plain string aliases (`AliasFactory.for_string`), not alternate-part cross-references. That's a real gap against the questionnaire's stated goal ("model relationships") and needs resolving before this plan is treated as complete.

## Reused building blocks (from exploration)

- `PartFactory.create(data=, actor=)` — `app/parts/control_layer/factories/part_factory.py`
- `PartManufacturerManager.create` / resolve-by-name-iexact idiom copied from `PartBulkUploadFactory._resolve_manufacturer` — `app/parts/control_layer/managers/part_manufacturer_manager.py`, `app/parts/control_layer/factories/part_bulk_upload_factory.py:104`
- `SupplierItemManager.create(data=, actor=)` — `app/parts/control_layer/managers/supplier_item_manager.py`
- `AliasFactory.for_string(part, alias, alias_type, source=, actor=)` — `app/parts/control_layer/factories/alias_factory.py`
- `PartDomainManager(part, actor).add_domain(domain_id)` — `app/parts/control_layer/managers/part_domain_manager.py`
- `administration.Domain` lookup by slug — `app/administration/models/data_ownership/domains.py` (`slug` is the unique field)
- Result-list / per-row-transaction / results-table pattern — `PartBulkUploadFactory` + `BulkUploadRowResult` + `parts/bulk_upload.html` (`app/parts/control_layer/factories/part_bulk_upload_factory.py`, `app/parts/templates/parts/bulk_upload.html`)
- File-download-with-`Content-Disposition` pattern — `app/events/presentation_layer/entrypoints/files.py:96-103` (`file_download`)
- `<file-upload>` web component contract — `harness/UX_UI/components/file_upload.md` (must be inside `enctype="multipart/form-data"` form; server reads `request.FILES.getlist(name)`)
- Form action-button layout — `harness/UX_UI/form_style_guide.md` (submit bottom-right in card-footer, cancel bottom-left)
- Functional-view + F5-rule pattern — every existing Parts entrypoint is a plain `@require_http_methods` function view, not a CBV; this stays consistent.

## New files / changes

**1. `requirements.txt`** — add `defusedxml>=0.7,<0.8`. The XML is user-uploaded; stdlib `xml.etree.ElementTree` is vulnerable to entity-expansion (billion-laughs) DoS, so parsing goes through `defusedxml.ElementTree` instead.

**2. `app/parts/xml_schema/parts_bulk_upload.xsd`** (new folder) — a real XSD matching the structure above, served as the downloadable reference file. It documents the shape but is **not** used for server-side validation at runtime (avoids adding an `xmlschema` dependency for marginal benefit) — our own adaptor/guard checks do the real validation and produce friendlier per-field messages.

**3. `app/parts/control_layer/adapters/part_xml_upload_adaptor.py`** — new Adaptor.
- `PartXmlUploadAdaptor.parse(uploaded_file) -> tuple[list[dict], list[str]]`
- Size guard (reject > 5 MB) before parsing.
- Parses with `defusedxml.ElementTree.parse`; catches `ParseError`/`DefusedXmlException` and returns `([], ["top-level error message"])`.
- Verifies root tag is `partset`; walks each `<part>` into a plain dict:
  ```python
  {
    "identity": {"part_number":, "name":, "description":, "part_type":, "category":, "is_active":},
    "supplier_items": [{"manufacturer_part_number":, "name":, "is_active":, "description":,
                          "manufacturer": {"name":, "code":, "website":}}, ...],
    "aliases": [{"value":, "type":}, ...],
    "domains": [{"slug":, "title":}, ...],
  }
  ```
- No validation logic here beyond structural parsing (attribute presence is checked downstream by existing guards) — mirrors `PartBulkUploadAdaptor`'s "adaptor only shapes data" scope.

**4. `app/parts/control_layer/factories/part_xml_upload_factory.py`** — new BulkFactory, sibling to `PartBulkUploadFactory`.
- `PartXmlUploadRowResult` dataclass: `part_index, part_number, ok, part_id=None, errors=None`.
- `PartXmlUploadFactory.create_many(cls, *, parts: list[dict], actor) -> list[PartXmlUploadRowResult]` — loops `_create_row` per part.
- `_create_row`: single `transaction.atomic()` wrapping:
  1. `PartFactory.create(data=row["identity"], actor=actor)`
  2. For each supplier-item block: resolve manufacturer (`PartManufacturer.objects.filter(name__iexact=...).first()` else `PartManufacturerManager.create(...)`), then `SupplierItemManager.create(...)`.
  3. For each alias: `AliasFactory.for_string(part, value, type or "IMPORTED", source=AliasSource.MANUAL, actor=actor)`.
  4. For each domain: `Domain.objects.filter(slug=slug).first()`; if `None`, raise a local `DomainNotFoundError(["Domain with slug 'X' not found."])`; else `PartDomainManager(part, actor).add_domain(domain.id)`. `title` is display-only and not cross-checked against `domain.name` — keeps the resolution logic to one clear rule (slug is authoritative) instead of a partial warning mechanism.
  5. Catch `PartValidationError`, `SupplierItemValidationError`, `PartManufacturerValidationError`, `AliasValidationError`, `DomainNotFoundError` → convert to failed `PartXmlUploadRowResult`, transaction rolls back.

**5. `app/parts/presentation_layer/entrypoints/parts_bulk_upload_xml.py`** — new entrypoint module, two function views:
- `part_bulk_upload_xml(request)`: `GET` renders the explainer + upload form (`submitted: False`). `POST` reads `request.FILES.get("file")`, calls `PartXmlUploadAdaptor.parse`; if top-level errors, render with `parse_errors`; else `PartXmlUploadFactory.create_many(parts=rows, actor=request.user)`, split succeeded/failed, render `submitted: True`.
- `part_bulk_upload_xml_schema(request)`: `GET` only, serves `app/parts/xml_schema/parts_bulk_upload.xsd` via `FileResponse(..., as_attachment=True, filename="parts_bulk_upload.xsd")`, same `Content-Disposition` shape as `events/.../files.py:file_download`.

**6. `app/parts/urls.py`** — add:
```python
path("bulk-upload/xml/", part_bulk_upload_xml, name="part_bulk_upload_xml"),
path("bulk-upload/xml/schema/", part_bulk_upload_xml_schema, name="part_bulk_upload_xml_schema"),
```
plus imports.

**7. `app/parts/templates/parts/bulk_upload_xml.html`** — new template, `{% extends "parts/base.html" %}`, structure mirrors `bulk_upload.html`:
- Page hero explaining the feature.
- "Not submitted" state: one card explaining the structure (bullet list of elements/attributes + a `<pre>`-rendered example matching the XML above) with a "Download XSD" link (`{% url 'part_bulk_upload_xml_schema' %}`), then a second card with the upload form: `<form method="post" enctype="multipart/form-data">{% csrf_token %}<file-upload name="file" accept=".xml" label="XML file"></file-upload>`, submit button in a card-footer per `form_style_guide.md` (primary bottom-right, Cancel bottom-left).
- "Submitted" state: same succeeded/failed results table pattern as `bulk_upload.html` (`Row | Part Number | Errors`), plus a banner for top-level parse errors if the file itself was invalid XML.

**8. `app/parts/templates/parts/base.html`** — add a `{% block nav_bulk_upload_xml %}` sidebar link next to the existing "Bulk Upload" entry (line ~31), pointing at `part_bulk_upload_xml`.

**9. `app/parts/tests/test_xml_bulk_upload.py`** — focused control-layer tests per `harness/Architecture/tests.md` ("Control layer... every Context and Handler gets a focused test"): happy path (part + 2 supplier items + alias + domain created), a malformed-XML top-level error, an unknown-domain-slug causing whole-part rollback, and a duplicate `part_number` failing cleanly.

No migrations needed — no schema changes.

## Verification

1. `python manage.py check` — catch import/wiring errors.
2. Run new tests: `pytest app/parts/tests/test_xml_bulk_upload.py -v`.
3. Manual: start dev server, log in, visit `/parts/bulk-upload/xml/`, download the XSD, upload a valid sample XML (2 parts, one with 2 supplier items + aliases + a domain that exists in seed data) and confirm both parts + their revisions/supplier-items/aliases appear correctly on `/parts/<id>/`; then upload one with a bad domain slug and confirm the whole part is reported as failed with no partial rows created.
