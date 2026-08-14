# Initial Prompt

Verbatim request that seeded this kit (passed to the Kit Builder as its invocation arguments):

> create a page http://localhost:8000/parts/bulk-upload/XML
> goal user can upload an xml document that can upload all of the information for a part and model relationships
> make a planning document for this
> Things ill need
> an xmr document on the page
> instructions on how to structure the data
> an xml ingestion class

(Spelling corrected per project convention: "an xmr document" → "an XML document"; "upload all of the information" is read as "encode all of the information" — the document is uploaded once, and everything it describes is created from it in one pass.)

## Referenced seed material

- This request arrived immediately after a prior working session (same conversation) that built
  the existing **CSV/paste-grid bulk upload** at `/parts/bulk-upload/` — a table-paste flow that
  creates one simple part (identity + one manufacturer + one supplier item) per row. That feature's
  control-layer shape is directly relevant prior art for this kit:
  - [app/parts/control_layer/adapters/part_bulk_upload_adaptor.py](../app/parts/control_layer/adapters/part_bulk_upload_adaptor.py)
  - [app/parts/control_layer/factories/part_bulk_upload_factory.py](../app/parts/control_layer/factories/part_bulk_upload_factory.py)
  - [app/parts/presentation_layer/entrypoints/parts_bulk_upload.py](../app/parts/presentation_layer/entrypoints/parts_bulk_upload.py)
  - [app/parts/templates/parts/bulk_upload.html](../app/parts/templates/parts/bulk_upload.html)

  That same session also added a hard rule to `/parts/new/` (and to the CSV bulk path): a part
  cannot be created without at least one manufacturer + supplier item. Whatever this kit's XML
  ingestion class does, it inherits that same constraint unless explicitly reversed here.

- The CSV path only ever produces a **flat, single-part-per-row** shape — it has no way to express
  relationships *between* parts (e.g. one part referencing another). The stated goal of this kit —
  "model relationships" — is the capability gap the CSV path cannot fill, and is the reason a
  second, XML-based ingestion path is being considered rather than extending the CSV grid.

- Existing domain model this kit's XML documents will need to produce records against: `Part`,
  `PartManufacturer`, `SupplierItem` (see [docs/parts.md](../docs/parts.md) and
  [docs/core_domain.md](../docs/core_domain.md)). What "relationships between parts" concretely
  means — BOM/assembly composition, alternates/substitutes, cross-references, something else
  entirely, or several of these — is **not yet defined** and is the central open question this
  kit exists to resolve.

## Explicitly out of scope for this prompt (assumed, to be confirmed in the questionnaire)

- The exact route/page (`/parts/bulk-upload/xml/` vs. some other path), its navigation entry, and
  its on-page layout are **front-end kit** territory, not this kit's — this kit stops at "the
  backend could theoretically ingest this XML document and produce the described records." The
  page shown to the user (upload control, on-page schema reference, instructions) is a *thin*
  consumer of whatever this kit's ingestion class produces; the kit should still describe what
  that page needs from the backend (e.g. an example/schema document to display, a
  structured error report to render) even though it does not design the page itself.
