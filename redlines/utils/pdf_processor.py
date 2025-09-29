from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import Any, Optional

from .markdown_processor import MarkdownProcessor
from .styles import Styles

try:  # pragma: no cover - optional dependency path
    from weasyprint import HTML as WeasyHTML
except ImportError:  # pragma: no cover - optional dependency path
    WeasyHTML = None

try:  # pragma: no cover - optional dependency path
    from xhtml2pdf import pisa
except ImportError:  # pragma: no cover - optional dependency path
    pisa = None

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Bidirectional PDF conversion with async orchestration and fallbacks.

    The processor can render Markdown/HTML/text into PDFs while also extracting
    Markdown or text from uploaded PDF payloads.  Multiple rendering backends
    are supported (WeasyPrint and xhtml2pdf) and each conversion runs within a
    bounded semaphore to avoid overwhelming the runtime.
    """

    def __init__(
        self,
        *,
        styles: Optional[Styles] = None,
        markdown_processor: Optional[MarkdownProcessor] = None,
        weasyprint_enabled: bool = True,
        xhtml2pdf_enabled: bool = True,
        max_concurrent_operations: int = 4,
    ) -> None:
        self.styles = styles or Styles()
        self.markdown_processor = markdown_processor or MarkdownProcessor()
        self.weasyprint_enabled = weasyprint_enabled and WeasyHTML is not None
        self.xhtml2pdf_enabled = xhtml2pdf_enabled and pisa is not None
        self._semaphore = asyncio.Semaphore(max_concurrent_operations)

        if not (self.weasyprint_enabled or self.xhtml2pdf_enabled):
            msg = 'No PDF rendering backend available. Install weasyprint or xhtml2pdf.'
            raise RuntimeError(msg)

    # ------------------------------------------------------------------
    # Rendering into PDF
    # ------------------------------------------------------------------
    async def markdown_to_pdf(
        self,
        markdown_content: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
        prefer_backend: Optional[str] = None,
    ) -> bytes:
        """Render Markdown into a PDF document."""
        html_fragment = await self.markdown_processor.to_html(markdown_content, hard_wrap=True)
        html_document = self.styles.build_html_document(html_fragment, metadata)
        return await self._html_document_to_pdf(html_document, prefer_backend)

    async def html_to_pdf(
        self,
        html_content: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
        treat_as_fragment: bool = True,
        prefer_backend: Optional[str] = None,
    ) -> bytes:
        """Transform HTML into PDF, optionally wrapping fragments with default styles."""
        if treat_as_fragment:
            html_document = self.styles.build_html_document(html_content, metadata)
        else:
            html_document = html_content
        return await self._html_document_to_pdf(html_document, prefer_backend)

    async def text_to_pdf(
        self,
        text_content: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
        prefer_backend: Optional[str] = None,
    ) -> bytes:
        """Convert plain text into PDF via Markdown normalisation."""
        markdown = await self.markdown_processor.from_text(text_content)
        return await self.markdown_to_pdf(markdown, metadata=metadata, prefer_backend=prefer_backend)

    # ------------------------------------------------------------------
    # Extracting from PDF
    # ------------------------------------------------------------------
    async def pdf_to_markdown(self, payload: bytes) -> str:
        """Extract Markdown content from a PDF payload."""
        markdown = await self.markdown_processor.from_pdf(payload)
        if not markdown.strip():
            msg = 'Unable to extract textual content from PDF payload.'
            raise ValueError(msg)
        return markdown

    async def pdf_to_text(self, payload: bytes) -> str:
        """Extract plain text from a PDF payload."""
        markdown = await self.pdf_to_markdown(payload)
        return await self.markdown_processor.to_text(markdown)

    async def pdf_to_html(
        self, payload: bytes, *, metadata: Optional[dict[str, Any]] = None
    ) -> str:
        """Extract HTML from a PDF payload by way of Markdown rendering."""
        markdown = await self.pdf_to_markdown(payload)
        html_fragment = await self.markdown_processor.to_html(markdown, hard_wrap=True)
        return self.styles.build_html_document(html_fragment, metadata)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _html_document_to_pdf(self, html_document: str, prefer_backend: Optional[str]) -> bytes:
        async with self._semaphore:
            backends = self._ordered_backends(prefer_backend)
            last_exception: Optional[Exception] = None
            for backend in backends:
                try:
                    if backend == 'weasyprint' and self.weasyprint_enabled:
                        return await self._render_weasyprint(html_document)
                    if backend == 'xhtml2pdf' and self.xhtml2pdf_enabled:
                        return await self._render_xhtml2pdf(html_document)
                except Exception as exc:  # pragma: no cover - backend specific failures
                    logger.warning('PDF backend %s failed: %s', backend, exc)
                    last_exception = exc
            msg = 'All PDF rendering backends failed.'
            raise RuntimeError(msg) from last_exception

    def _ordered_backends(self, prefer_backend: Optional[str]) -> list[str]:
        if prefer_backend == 'xhtml2pdf':
            return ['xhtml2pdf', 'weasyprint']
        return ['weasyprint', 'xhtml2pdf']

    async def _render_weasyprint(self, html_document: str) -> bytes:
        if WeasyHTML is None:  # pragma: no cover - defensive, should not happen if enabled
            msg = 'WeasyPrint backend unavailable'
            raise RuntimeError(msg)

        def _render() -> bytes:
            return WeasyHTML(string=html_document).write_pdf()

        return await asyncio.to_thread(_render)

    async def _render_xhtml2pdf(self, html_document: str) -> bytes:
        if pisa is None:  # pragma: no cover - defensive, should not happen if enabled
            msg = 'xhtml2pdf backend unavailable'
            raise RuntimeError(msg)

        output = BytesIO()

        def _render():
            # xhtml2pdf expects bytes and writes into provided buffer
            return pisa.CreatePDF(html_document, dest=output)

        status = await asyncio.to_thread(_render)
        if status.err:
            output.close()
            msg = f'xhtml2pdf conversion error: {status.err}'
            raise RuntimeError(msg)
        output.seek(0)
        pdf_bytes = output.read()
        output.close()
        return pdf_bytes


__all__ = ['PDFProcessor']
