"""Shared control-layer exceptions for the parts app.

``PartValidationError`` is raised on both the create path (``PartFactory``) and
the edit path (``PartManager``); it lives here so both import the *same* class
rather than each declaring an identical copy (which previously forced callers to
alias one import to avoid a name collision)."""

from __future__ import annotations


class PartValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))
