from __future__ import annotations

import asyncio
import contextlib
import copy
import logging
import re
from enum import Enum
from io import BytesIO
from typing import Any, Optional

from docx import Document
from docx.document import Document as DocumentType
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
try:  # pragma: no cover - optional dependency
    from html4docx import HtmlToDocx
except ImportError:  # pragma: no cover - optional dependency
    HtmlToDocx = None

from .markdown_processor import MarkdownProcessor
from .styles import Styles

logger = logging.getLogger(__name__)

DOCX_DEFAULT_TABLE_STYLE = 'Table Grid'


class DocxProcessingMethod(Enum):
    HTML4DOCX = 'html4docx'
    MANUAL = 'manual'


class DOCXProcessor:
    """High-fidelity DOCX conversion pipeline with async orchestration."""

    def __init__(
        self,
        *,
        styles: Optional[Styles] = None,
        markdown_processor: Optional[MarkdownProcessor] = None,
        html4docx_enabled: bool = True,
        manual_enabled: bool = True,
        preferred_method: DocxProcessingMethod = DocxProcessingMethod.HTML4DOCX,
        max_concurrent_operations: int = 6,
    ) -> None:
        self.styles = styles or Styles()
        self.markdown_processor = markdown_processor or MarkdownProcessor()
        self.html4docx_enabled = html4docx_enabled and HtmlToDocx is not None
        self.manual_enabled = manual_enabled
        self.preferred_method = preferred_method
        self._semaphore = asyncio.Semaphore(max_concurrent_operations)
        self._table_style = DOCX_DEFAULT_TABLE_STYLE

    # ------------------------------------------------------------------
    # Public conversion API
    # ------------------------------------------------------------------
    async def markdown_to_docx(
        self,
        markdown_content: str,
        *,
        method: Optional[DocxProcessingMethod] = None,
    ) -> bytes:
        async with self._semaphore:
            conversion_order = self._conversion_order(method)
            html = await self.markdown_processor.to_html(markdown_content, hard_wrap=True)
            for approach in conversion_order:
                try:
                    if approach is DocxProcessingMethod.HTML4DOCX and self.html4docx_enabled:
                        return await self._html_to_docx_html4docx(html)
                    if approach is DocxProcessingMethod.MANUAL and self.manual_enabled:
                        return await self._markdown_to_docx_manual(markdown_content)
                except Exception as exc:
                    logger.debug('%s conversion failed: %s', approach.value, exc)
                    continue
            msg = 'All DOCX conversion strategies failed'
            raise RuntimeError(msg)

    async def html_to_docx(
        self,
        html_content: str,
        *,
        method: Optional[DocxProcessingMethod] = None,
    ) -> bytes:
        async with self._semaphore:
            conversion_order = self._conversion_order(method)
            for approach in conversion_order:
                try:
                    if approach is DocxProcessingMethod.HTML4DOCX and self.html4docx_enabled:
                        return await self._html_to_docx_html4docx(html_content)
                    if approach is DocxProcessingMethod.MANUAL and self.manual_enabled:
                        markdown = await self.markdown_processor.from_html(html_content)
                        return await self._markdown_to_docx_manual(markdown)
                except Exception as exc:
                    logger.debug('%s conversion failed: %s', approach.value, exc)
                    continue
            msg = 'All DOCX conversion strategies failed'
            raise RuntimeError(msg)

    async def text_to_docx(
        self,
        text_content: str,
        *,
        method: Optional[DocxProcessingMethod] = None,
    ) -> bytes:
        markdown = await self.markdown_processor.from_text(text_content)
        return await self.markdown_to_docx(markdown, method=method)

    async def docx_to_markdown(self, payload: bytes) -> str:
        return await self.markdown_processor.from_docx(payload)

    async def docx_to_text(self, payload: bytes) -> str:
        markdown = await self.docx_to_markdown(payload)
        return await self.markdown_processor.to_text(markdown)

    async def docx_to_html(self, payload: bytes) -> str:
        markdown = await self.docx_to_markdown(payload)
        return await self.markdown_processor.to_html(markdown)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _conversion_order(self, preferred: Optional[DocxProcessingMethod]) -> list[DocxProcessingMethod]:
        if preferred:
            base = [preferred]
        else:
            base = [self.preferred_method]
        fallback = DocxProcessingMethod.MANUAL if base[0] is DocxProcessingMethod.HTML4DOCX else DocxProcessingMethod.HTML4DOCX
        return base + [fallback]

    async def _html_to_docx_html4docx(self, html_content: str) -> bytes:
        if HtmlToDocx is None:  # pragma: no cover - defensive
            msg = 'html4docx backend is not available'
            raise RuntimeError(msg)
        parser = HtmlToDocx()
        with contextlib.suppress(Exception):
            parser.table_style = self._table_style
        document = await asyncio.to_thread(parser.parse_html_string, html_content)
        self.styles.configure_document(document)
        self._append_configured_text(document)
        buffer = BytesIO()
        await asyncio.to_thread(document.save, buffer)
        buffer.seek(0)
        return buffer.read()

    async def _markdown_to_docx_manual(self, markdown_text: str) -> bytes:
        doc = Document()
        self.styles.configure_document(doc)

        lines = markdown_text.split('\n')
        current_paragraph = None
        in_code_block = False
        code_block_content: list[str] = []
        table_data: list[list[str]] = []
        in_table = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith('```'):
                if in_code_block:
                    code_text = '\n'.join(code_block_content)
                    paragraph = doc.add_paragraph()
                    self._format_paragraph(paragraph)
                    run = paragraph.add_run(code_text)
                    run.font.name = 'Courier New'
                    run.font.size = Pt(10)
                    in_code_block = False
                    code_block_content = []
                else:
                    in_code_block = True
                current_paragraph = None
                continue

            if in_code_block:
                code_block_content.append(line)
                continue

            if not stripped:
                current_paragraph = None
                continue

            if stripped.startswith('|') and stripped.endswith('|'):
                if not in_table:
                    in_table = True
                    table_data = []
                cells = [cell.strip() for cell in stripped.strip('|').split('|')]
                if all(re.fullmatch(r'[:\-]+', cell) for cell in cells):
                    continue
                table_data.append(cells)
                continue
            if in_table:
                self._add_table(doc, table_data)
                table_data = []
                in_table = False

            if stripped.startswith('#'):
                level = len(stripped) - len(stripped.lstrip('#'))
                content = stripped[level:].strip()
                paragraph = doc.add_heading(content, level=min(level, 6))
                self.styles.apply_heading(paragraph, min(level, 6))
                current_paragraph = None
                continue

            # Ordered list
            if re.match(r'^\d+\.\s+', stripped):
                content = re.sub(r'^\d+\.\s+', '', stripped)
                paragraph = doc.add_paragraph(content, style='List Number')
                self._format_paragraph(paragraph)
                current_paragraph = None
                continue

            # Unordered list
            if stripped.startswith(('- ', '* ', '+ ')):
                content = re.sub(r'^[\-\*\+]\s+', '', stripped)
                paragraph = doc.add_paragraph(content, style='List Bullet')
                self._format_paragraph(paragraph)
                current_paragraph = None
                continue

            if stripped.startswith('>'):
                content = stripped.lstrip('>').strip()
                paragraph = doc.add_paragraph()
                paragraph.paragraph_format.left_indent = Pt(24)
                paragraph.paragraph_format.right_indent = Pt(24)
                self._format_paragraph(paragraph)
                self._add_inline_markdown(paragraph, content)
                current_paragraph = None
                continue

            if current_paragraph is None:
                current_paragraph = doc.add_paragraph()
                self._format_paragraph(current_paragraph)
            else:
                current_paragraph.add_run(' ')
            self._add_inline_markdown(current_paragraph, stripped)

        if in_table and table_data:
            self._add_table(doc, table_data)

        self._append_configured_text(doc)

        buffer = BytesIO()
        await asyncio.to_thread(doc.save, buffer)
        buffer.seek(0)
        return buffer.read()

    def _add_table(self, doc: DocumentType, data: list[list[str]]) -> None:
        if not data:
            return
        rows = len(data)
        cols = len(data[0])
        table_obj = doc.add_table(rows=rows, cols=cols)
        table_obj.style = self._table_style

        for r_idx, row_data in enumerate(data):
            for c_idx, cell_text in enumerate(row_data):
                cell = table_obj.cell(r_idx, c_idx)
                cell.text = cell_text
                for paragraph in cell.paragraphs:
                    self._format_paragraph(paragraph)
                    for run in paragraph.runs:
                        run.font.bold = r_idx == 0

    def _add_inline_markdown(self, paragraph, text: str) -> None:
        pattern = r'(\*\*(.+?)\*\*)|(\*(.+?)\*)|(__(.+?)__)|(\_(.+?)\_)|(`(.+?)`)'  # bold, italic, code
        position = 0
        for match in re.finditer(pattern, text):
            if match.start() > position:
                self._add_plain_run(paragraph, text[position : match.start()])
            if match.group(1):
                self._add_bold_run(paragraph, match.group(2))
            elif match.group(3):
                self._add_italic_run(paragraph, match.group(4))
            elif match.group(5):
                self._add_bold_run(paragraph, match.group(6))
            elif match.group(7):
                self._add_italic_run(paragraph, match.group(8))
            elif match.group(9):
                run = paragraph.add_run(match.group(10))
                run.font.name = 'Courier New'
                run.font.size = Pt(10)
            position = match.end()
        if position < len(text):
            self._add_plain_run(paragraph, text[position:])

    def _add_plain_run(self, paragraph, content: str) -> None:
        run = paragraph.add_run(content)
        self._format_run(run)

    def _add_bold_run(self, paragraph, content: str) -> None:
        run = paragraph.add_run(content)
        self._format_run(run, {'bold': True})

    def _add_italic_run(self, paragraph, content: str) -> None:
        run = paragraph.add_run(content)
        self._format_run(run, {'italic': True})

    def _format_paragraph(self, paragraph) -> None:
        self.styles.apply_paragraph_defaults(paragraph)

    def _append_configured_text(self, document: DocumentType) -> None:
        append_text = self.styles.config.get('append_text') or ''
        if not append_text.strip():
            return
        for line in append_text.split('\n'):
            paragraph = document.add_paragraph(line)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            self._format_paragraph(paragraph)

    def _format_run(self, run, overrides: Optional[dict[str, Any]] = None) -> None:
        font_cfg = copy.deepcopy(self.styles.config.get('font', {}))
        if overrides:
            Styles._deep_update(font_cfg, overrides)
        Styles._apply_run_font(run.font, font_cfg)


__all__ = ['DOCXProcessor', 'DocxProcessingMethod']
