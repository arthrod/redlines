from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import Optional

import mistune
from bs4 import BeautifulSoup
from mistune.plugins.abbr import abbr
from mistune.plugins.def_list import def_list
from mistune.plugins.footnotes import footnotes
from mistune.plugins.formatting import insert, mark, strikethrough, subscript, superscript
from mistune.plugins.table import table
from mistune.plugins.task_lists import task_lists
from mistune.plugins.url import url

try:
    import markitdown
except ImportError:  # pragma: no cover - dependency optional in some installs
    markitdown = None

try:
    from docling.document_converter import DocumentConverter
    from docling_core.types.io import DocumentStream
except ImportError:  # pragma: no cover - dependency optional in some installs
    DocumentConverter = None
    DocumentStream = None

try:
    import markdownify
except ImportError:  # pragma: no cover
    markdownify = None

try:
    from docx import Document as PythonDocxDocument
except ImportError:  # pragma: no cover - optional dependency path
    PythonDocxDocument = None


logger = logging.getLogger(__name__)

MISTUNE_PLUGINS = [
    strikethrough,
    footnotes,
    table,
    task_lists,
    insert,
    def_list,
    abbr,
    mark,
    subscript,
    url,
    superscript,
]


class MarkdownProcessor:
    """Convert to and from Markdown using high-fidelity pipelines.

    The processor mirrors the behaviour of the original monolithic converter but
    exposes the building blocks as reusable pieces. Every potentially blocking
    operation is funnelled through :func:`asyncio.to_thread` so callers keep
    their event loops responsive.
    """

    def __init__(
        self, *, enable_docling: bool = True, enable_markitdown: bool = True, max_concurrent_tasks: int = 6
    ) -> None:
        """Initialise the processor with optional extraction backends."""
        self.enable_docling = enable_docling and DocumentConverter is not None and DocumentStream is not None
        self.enable_markitdown = enable_markitdown and markitdown is not None
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._markdown_to_html = mistune.create_markdown(renderer=mistune.HTMLRenderer(), plugins=MISTUNE_PLUGINS)

    # ------------------------------------------------------------------
    # Markdown renderers
    # ------------------------------------------------------------------
    async def to_html(self, markdown_content: str, *, hard_wrap: bool = True) -> str:
        """Render Markdown into HTML, honouring optional hard wrap behaviour."""
        renderer = (
            mistune.create_markdown(renderer=mistune.HTMLRenderer(), plugins=MISTUNE_PLUGINS, hard_wrap=True)
            if hard_wrap
            else self._markdown_to_html
        )
        result = renderer(markdown_content)
        return result if isinstance(result, str) else str(result)

    async def to_text(self, markdown_content: str) -> str:
        """Return a plain-text representation of ``markdown_content``."""
        html = await self.to_html(markdown_content)
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text('\n', strip=True)

    async def from_html(self, html_content: str) -> str:
        """Convert HTML into Markdown using :mod:`markdownify`."""
        if markdownify is None:
            msg = 'markdownify is required for HTML to Markdown conversion'
            raise RuntimeError(msg)

        async with self._semaphore:
            return await asyncio.to_thread(markdownify.markdownify, html_content, heading_style='ATX')

    async def from_text(self, text_content: str) -> str:
        # Preserve line breaks while ensuring consistent newline usage
        return text_content.replace('\r\n', '\n').replace('\r', '\n')

    async def from_docx(self, payload: bytes) -> str:
        """Extract Markdown from a DOCX payload using progressive fallbacks."""
        async with self._semaphore:
            text = await self._docling_to_markdown(payload, 'document.docx')
            if text:
                return text
            text = await self._markitdown_to_markdown(payload)
            if text:
                return text
            if PythonDocxDocument is not None:
                text = await self._python_docx_to_markdown(payload)
                if text:
                    return text
        if PythonDocxDocument is not None:
            fallback = await self._python_docx_to_markdown(payload)
            if fallback.strip():
                return fallback
        logger.warning('Falling back to empty result for DOCX payload - upstream extractors unavailable')
        return ''

    async def from_pdf(self, payload: bytes) -> str:
        """Extract Markdown from a PDF payload using progressive fallbacks."""
        async with self._semaphore:
            text = await self._docling_to_markdown(payload, 'document.pdf')
            if text:
                return text
            text = await self._markitdown_to_markdown(payload)
            if text:
                return text
        logger.warning('Falling back to empty result for PDF payload - upstream extractors unavailable')
        return ''

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _docling_to_markdown(self, payload: bytes, name: str) -> Optional[str]:
        """Try Docling for structured extraction, returning ``None`` when unavailable."""
        if not self.enable_docling or DocumentConverter is None or DocumentStream is None:
            return None

        try:
            converter = DocumentConverter()
            stream = DocumentStream(name=name, stream=BytesIO(payload))
            result = await asyncio.to_thread(converter.convert, stream)
        except Exception as exc:  # pragma: no cover - docling heavy path
            logger.debug('Docling conversion failed for %s: %s', name, exc)
            return None

        document = getattr(result, 'document', None)
        if not document:
            return None

        for extractor in ('export_to_html', 'export_to_markdown', 'export_to_text'):
            if hasattr(document, extractor):
                try:
                    result_text = await asyncio.to_thread(getattr(document, extractor))
                    if not result_text or not str(result_text).strip():
                        continue
                    if extractor == 'export_to_html':
                        markdown_result = await self._html_to_markdown_async(str(result_text))
                        if markdown_result.strip():
                            logger.info('Docling %s succeeded for %s', extractor, name)
                            return markdown_result
                        continue
                    logger.info('Docling %s succeeded for %s', extractor, name)
                    return str(result_text)
                except Exception as exc:  # pragma: no cover - docling heavy path
                    logger.debug('Docling %s failed for %s: %s', extractor, name, exc)
        return None

    async def _markitdown_to_markdown(self, payload: bytes) -> Optional[str]:
        """Fallback to :mod:`markitdown` for lightweight conversions."""
        if not self.enable_markitdown:
            return None
        if markitdown is None:
            return None
        try:
            converter = markitdown.MarkItDown(enable_plugins=True)
            result = await asyncio.to_thread(converter.convert_stream, BytesIO(payload))
            text_content = getattr(result, 'text_content', None)
            if text_content and text_content.strip():
                logger.info('MarkItDown extraction succeeded')
                return text_content
        except Exception as exc:  # pragma: no cover - optional dependency path
            logger.debug('MarkItDown conversion failed: %s', exc)
        return None

    async def _html_to_markdown_async(self, html_content: str) -> str:
        if markdownify is None:
            return ''
        return await asyncio.to_thread(markdownify.markdownify, html_content, heading_style='ATX')

    async def _python_docx_to_markdown(self, payload: bytes) -> str:
        """Final DOCX fallback using :mod:`python-docx` when other tools fail."""
        if PythonDocxDocument is None:  # pragma: no cover - defensive
            return ''

        def _extract() -> str:
            doc_class = PythonDocxDocument  # Added for type safety
            assert doc_class is not None, 'PythonDocxDocument is None'
            document = doc_class(BytesIO(payload))
            lines: list[str] = []
            for paragraph in document.paragraphs:
                text = paragraph.text.strip()
                if text:
                    lines.append(text)
            return '\n\n'.join(lines)

        return await asyncio.to_thread(_extract)
