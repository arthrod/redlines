from __future__ import annotations

from enum import Enum


class DiffBackend(str, Enum):
    """Available diff/conversion backends for Redlines."""

    HTML_TODOCX = "htmltodocx"
    DOCLING_STRUCTURED = "docling"
    XMLDIFF_ONLY = "xmldiff"

    @classmethod
    def from_value(cls, value: str | 'DiffBackend') -> 'DiffBackend':
        if isinstance(value, cls):
            return value
        normalized = value.lower().replace('-', '').replace('_', '')
        for member in cls:
            key = member.value.replace('-', '').replace('_', '')
            if normalized == key:
                return member
        raise ValueError(f"Unknown diff backend: {value}")
