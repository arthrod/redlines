from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from docx.oxml import OxmlElement
from docx.oxml.ns import qn


class TrackChangesBuilder:
    """Utility to generate DOCX track changes elements with rich run support."""

    def __init__(self, *, author: str = 'Redlines', revision_start: int = 1) -> None:
        self.author = author
        self._revision_counter = revision_start

    def create_insertion(
        self, runs: str | Iterable[dict[str, object]], *, date: Optional[datetime] = None
    ) -> OxmlElement:
        """Return a ``w:ins`` element for the provided runs."""
        return self._create_change('w:ins', runs, date)

    def create_deletion(
        self, runs: str | Iterable[dict[str, object]], *, date: Optional[datetime] = None
    ) -> OxmlElement:
        """Return a ``w:del`` element for the provided runs."""
        return self._create_change('w:del', runs, date)

    def append_insertion(
        self, paragraph, runs: str | Iterable[dict[str, object]], *, date: Optional[datetime] = None
    ) -> None:
        """Append an insertion change to ``paragraph``."""
        paragraph._p.append(self.create_insertion(runs, date=date))  # type: ignore[attr-defined]

    def append_deletion(
        self, paragraph, runs: str | Iterable[dict[str, object]], *, date: Optional[datetime] = None
    ) -> None:
        """Append a deletion change to ``paragraph``."""
        paragraph._p.append(self.create_deletion(runs, date=date))  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _next_revision_id(self) -> int:
        current = self._revision_counter
        self._revision_counter += 1
        return current

    def _create_change(
        self, tag: str, runs: str | Iterable[dict[str, object]], date: Optional[datetime]
    ) -> OxmlElement:
        change = OxmlElement(tag)
        change.set(qn('w:id'), str(self._next_revision_id()))
        change.set(qn('w:author'), self.author)
        timestamp = (date or datetime.utcnow()).replace(microsecond=0).isoformat() + 'Z'
        change.set(qn('w:date'), timestamp)

        if isinstance(runs, str):
            runs = ({'text': runs},)

        for run_data in runs:
            run_el = self._build_run_element(run_data, deleted=(tag == 'w:del'))
            change.append(run_el)

        return change

    def _build_run_element(self, run_data: dict[str, object], *, deleted: bool) -> OxmlElement:
        run_el = OxmlElement('w:r')
        rpr = OxmlElement('w:rPr')

        if run_data.get('bold'):
            rpr.append(OxmlElement('w:b'))
        if run_data.get('italic'):
            rpr.append(OxmlElement('w:i'))
        if run_data.get('underline'):
            underline = OxmlElement('w:u')
            underline.set(qn('w:val'), 'single')
            rpr.append(underline)
        if run_data.get('strike'):
            rpr.append(OxmlElement('w:strike'))

        color = run_data.get('color')
        if color:
            color_el = OxmlElement('w:color')
            color_el.set(qn('w:val'), str(color))
            rpr.append(color_el)

        font = run_data.get('font')
        if font:
            rfonts = OxmlElement('w:rFonts')
            font_name = str(font)
            rfonts.set(qn('w:ascii'), font_name)
            rfonts.set(qn('w:hAnsi'), font_name)
            rpr.append(rfonts)

        size = run_data.get('size')
        if size:
            try:
                half_points = int(float(size) * 2)
                sz = OxmlElement('w:sz')
                sz.set(qn('w:val'), str(half_points))
                rpr.append(sz)
            except (TypeError, ValueError):
                pass

        if len(rpr):
            run_el.append(rpr)

        if run_data.get('break'):
            run_el.append(OxmlElement('w:br'))

        text = str(run_data.get('text', ''))
        text_tag = 'w:delText' if deleted else 'w:t'
        text_el = OxmlElement(text_tag)
        if text.startswith(' ') or text.endswith(' ') or '\n' in text:
            text_el.set(qn('xml:space'), 'preserve')
        text_el.text = text
        run_el.append(text_el)

        return run_el


__all__ = ['TrackChangesBuilder']
