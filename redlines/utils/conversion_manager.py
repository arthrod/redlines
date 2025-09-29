from __future__ import annotations

import asyncio
import threading
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .docx_processor import DOCXProcessor, DocxProcessingMethod
from .html_processor import HTMLProcessor
from .markdown_processor import MarkdownProcessor
from .pdf_processor import PDFProcessor
from .styles import Styles


class Format(Enum):
    TEXT = 'txt'
    MARKDOWN = 'md'
    PDF = 'pdf'
    DOCX = 'docx'
    HTML = 'html'

    @classmethod
    def normalize(cls, value: str) -> Format:
        """Return the canonical :class:`Format` for the provided string alias.

        The helper accepts MIME types and common shorthands (``pdf``, ``text/html`` etc.)
        so that higher-level APIs can stay forgiving about user input.
        """
        aliases = {
            'txt': cls.TEXT,
            'text': cls.TEXT,
            'plaintext': cls.TEXT,
            'md': cls.MARKDOWN,
            'markdown': cls.MARKDOWN,
            'mkd': cls.MARKDOWN,
            'pdf': cls.PDF,
            'application/pdf': cls.PDF,
            'docx': cls.DOCX,
            'doc': cls.DOCX,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': cls.DOCX,
            'html': cls.HTML,
            'htm': cls.HTML,
            'text/html': cls.HTML,
        }
        key = value.lower().strip()
        if key not in aliases:
            msg = f'Unsupported format: {value}'
            raise ValueError(msg)
        return aliases[key]


class ConversionManager:
    """Coordinate document conversions using specialised processors.

    The manager centralises the orchestration logic so callers interact with a
    single facade instead of juggling the PDF, HTML, DOCX and Markdown
    processors individually.  All conversions go through Markdown as the pivot
    format which keeps the cross-product of conversions manageable and easy to
    reason about.
    """

    def __init__(
        self,
        *,
        styles: Optional[Styles] = None,
        docx_method: DocxProcessingMethod = DocxProcessingMethod.HTML4DOCX,
        max_concurrent_operations: int = 6,
        markdown_processor: Optional[MarkdownProcessor] = None,
        docx_processor: Optional[DOCXProcessor] = None,
        pdf_processor: Optional[PDFProcessor] = None,
        html_processor: Optional[HTMLProcessor] = None,
    ) -> None:
        self.styles = styles or Styles()
        self.markdown_processor = markdown_processor or MarkdownProcessor()
        self.docx_processor = docx_processor or DOCXProcessor(
            styles=self.styles,
            markdown_processor=self.markdown_processor,
            preferred_method=docx_method,
            max_concurrent_operations=max_concurrent_operations,
        )
        self.pdf_processor = pdf_processor or PDFProcessor(
            styles=self.styles,
            markdown_processor=self.markdown_processor,
            max_concurrent_operations=max_concurrent_operations,
        )
        self.html_processor = html_processor or HTMLProcessor(
            styles=self.styles,
            markdown_processor=self.markdown_processor,
            max_concurrent_operations=max_concurrent_operations,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def convert(
        self,
        data: Any,
        source_format: str,
        target_format: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Convert ``data`` from ``source_format`` to ``target_format`` asynchronously.

        All heavy lifting is delegated to the specialised processors.  The
        method normalises the requested formats and funnels the content through
        Markdown, which acts as the canonical intermediate representation.
        """
        src_fmt = Format.normalize(source_format)
        tgt_fmt = Format.normalize(target_format)
        markdown = await self._to_markdown(data, src_fmt)
        return await self._from_markdown(markdown, tgt_fmt, metadata)

    async def extract_text(self, data: Any, source_format: str) -> str:
        """Return plain text extracted from ``data`` in ``source_format``."""
        src_fmt = Format.normalize(source_format)
        markdown = await self._to_markdown(data, src_fmt)
        return await self.markdown_processor.to_text(markdown)

    def convert_sync(
        self,
        data: Any,
        source_format: str,
        target_format: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Blocking wrapper around :meth:`convert` using :func:`asyncio.run`.

        The helper allows synchronous code paths (tests, CLI) to reuse the same
        conversion logic without having to manage an event loop explicitly.
        """
        return self._run_sync(self.convert(data, source_format, target_format, metadata=metadata))

    def extract_text_sync(self, data: Any, source_format: str) -> str:
        """Blocking variant of :meth:`extract_text`."""
        return self._run_sync(self.extract_text(data, source_format))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _to_markdown(self, data: Any, fmt: Format) -> str:
        """Convert ``data`` in ``fmt`` to Markdown, dispatching to processors."""
        if fmt is Format.MARKDOWN:
            return self._ensure_text(data)
        if fmt is Format.TEXT:
            text = self._ensure_text(data)
            return await self.markdown_processor.from_text(text)
        if fmt is Format.HTML:
            html = self._ensure_text(data)
            return await self.markdown_processor.from_html(html)
        if fmt is Format.DOCX:
            payload = self._ensure_bytes(data, fmt)
            return await self.docx_processor.docx_to_markdown(payload)
        if fmt is Format.PDF:
            payload = self._ensure_bytes(data, fmt)
            return await self.pdf_processor.pdf_to_markdown(payload)
        msg = f'Unsupported conversion from format {fmt.value}'
        raise ValueError(msg)

    async def _from_markdown(
        self, markdown: str, fmt: Format, metadata: Optional[dict[str, Any]]
    ) -> Any:
        """Generate the desired format ``fmt`` from a Markdown string."""
        if fmt is Format.MARKDOWN:
            return markdown
        if fmt is Format.TEXT:
            return await self.markdown_processor.to_text(markdown)
        if fmt is Format.HTML:
            return await self.html_processor.markdown_to_html_document(markdown, metadata=metadata)
        if fmt is Format.DOCX:
            return await self.docx_processor.markdown_to_docx(markdown)
        if fmt is Format.PDF:
            return await self.pdf_processor.markdown_to_pdf(markdown, metadata=metadata)
        msg = f'Unsupported conversion to format {fmt.value}'
        raise ValueError(msg)

    @staticmethod
    def _ensure_text(data: Any) -> str:
        """Coerce ``data`` into text, reading from paths when required."""
        if isinstance(data, str):
            path = Path(data)
            if path.exists():
                return path.read_text(encoding='utf-8')
            return data
        if isinstance(data, bytes):
            return data.decode('utf-8')
        if isinstance(data, Path):
            return data.read_text(encoding='utf-8')
        msg = 'Expected str, bytes, or Path for textual conversion'
        raise TypeError(msg)

    @staticmethod
    def _ensure_bytes(data: Any, fmt: Format) -> bytes:
        """Return ``data`` as raw bytes, loading from disk if a path is provided."""
        if isinstance(data, bytes):
            return data
        if isinstance(data, (str, Path)):
            path = Path(data)
            if path.exists():
                return path.read_bytes()
        msg = f'Binary conversion for {fmt.value} requires bytes or a valid file path'
        raise TypeError(msg)

    @staticmethod
    def _run_sync(coro):
        """Execute ``coro`` from synchronous code, preserving event loop safety."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result: dict[str, Any] = {}
        exc: list[BaseException] = []

        def runner() -> None:
            try:
                result['value'] = asyncio.run(coro)
            except BaseException as error:  # pragma: no cover - defensive
                exc.append(error)

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if exc:
            raise exc[0]
        return result.get('value')


__all__ = ['ConversionManager', 'Format']
