"""Configuration Management models — intentionally empty for now.

This app is currently a **presentation shell**. Every configuration and
capability model still lives under ``app/assets/models/`` and is served by
``app/assets`` entrypoints; this app only owns the section chrome (topnav tab,
sidebar) plus the serialized-part placeholder pages.

Planned residents (see ``docs/assets/tech_debt/configuration_section_extraction.md``):

* ``SerializedPart``           — a serial-numbered part instance installed on an asset
* ``SerializedPartTemplate``   — per-``assets.AssetModel`` declaration of expected serialized parts
* ``SerializedPartHistory``    — install/remove/transfer ledger for a ``SerializedPart``

New models belong **here**, not in ``app/assets``. Cross-app foreign keys use
lazy string references (``"assets.AssetModel"``, ``"parts.Part"``) exactly as
``app/dispatching/models/abstract_mixins.py`` already does.
"""
