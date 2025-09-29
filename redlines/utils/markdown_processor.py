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
    """Convert to/from markdown using high-fidelity pipelines.

    The implementation follows the legacy document converter/email_utils logic but removes
    product-specific branding and improves fallbacks. All potentially blocking operations
    run under an asyncio semaphore with ``asyncio.to_thread`` to avoid blocking callers.
    """

    def __init__(
        self,
        *,
        enable_docling: bool = True,
        enable_markitdown: bool = True,
        max_concurrent_tasks: int = 6,
    ) -> None:
        self.enable_docling = enable_docling and DocumentConverter is not None and DocumentStream is not None
        self.enable_markitdown = enable_markitdown and markitdown is not None
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._markdown_to_html = mistune.create_markdown(renderer=mistune.HTMLRenderer(), plugins=MISTUNE_PLUGINS)

    # ------------------------------------------------------------------
    # Markdown renderers
    # ------------------------------------------------------------------
    async def to_html(self, markdown_content: str, *, hard_wrap: bool = True) -> str:
        if hard_wrap:
            renderer = mistune.create_markdown(
                renderer=mistune.HTMLRenderer(), inline=mistune.InlineParser(hard_wrap=True), plugins=MISTUNE_PLUGINS
            )
        else:
            renderer = self._markdown_to_html
        return renderer(markdown_content)

    async def to_text(self, markdown_content: str) -> str:
        html = await self.to_html(markdown_content)
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text('\n', strip=True)

    async def from_html(self, html_content: str) -> str:
        if markdownify is None:
            msg = 'markdownify is required for HTML to Markdown conversion'
            raise RuntimeError(msg)

        async with self._semaphore:
            return await asyncio.to_thread(markdownify.markdownify, html_content, heading_style='ATX')

    async def from_text(self, text_content: str) -> str:
        # Preserve line breaks while ensuring consistent newline usage
        return text_content.replace('\r\n', '\n').replace('\r', '\n')

    async def from_docx(self, payload: bytes) -> str:
        async with self._semaphore:
            text = await self._docling_to_markdown(payload, 'document.docx')
            if text:
                return text
            text = await self._markitdown_to_markdown(payload)
            if text:
                return text
        logger.warning('Falling back to empty result for DOCX payload - upstream extractors unavailable')
        return ''

    async def from_pdf(self, payload: bytes) -> str:
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
        if not self.enable_docling:
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

        for extractor in ('export_to_markdown', 'export_to_text'):
            if hasattr(document, extractor):
                try:
                    result_text = await asyncio.to_thread(getattr(document, extractor))
                    if result_text and result_text.strip():
                        logger.info('Docling %s succeeded for %s', extractor, name)
                        return result_text
                except Exception as exc:  # pragma: no cover - docling heavy path
                    logger.debug('Docling %s failed for %s: %s', extractor, name, exc)
        return None

    async def _markitdown_to_markdown(self, payload: bytes) -> Optional[str]:
        if not self.enable_markitdown:
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
