from __future__ import annotations

import asyncio
import logging
from html import escape
from typing import Any, Optional

from bs4 import BeautifulSoup

from .markdown_processor import MarkdownProcessor
from .styles import Styles

logger = logging.getLogger(__name__)


class HTMLProcessor:
    """HTML conversion utilities built atop the shared markdown processor and styles."""

    def __init__(
        self,
        *,
        styles: Optional[Styles] = None,
        markdown_processor: Optional[MarkdownProcessor] = None,
        max_concurrent_operations: int = 6,
    ) -> None:
        self.styles = styles or Styles()
        self.markdown_processor = markdown_processor or MarkdownProcessor()
        self._semaphore = asyncio.Semaphore(max_concurrent_operations)

    # ------------------------------------------------------------------
    # Rendering into HTML documents
    # ------------------------------------------------------------------
    async def markdown_to_html_document(
        self, markdown_content: str, *, metadata: Optional[dict[str, Any]] = None, hard_wrap: bool = True
    ) -> str:
        fragment = await self.markdown_processor.to_html(markdown_content, hard_wrap=hard_wrap)
        return self.styles.build_html_document(fragment, metadata)

    async def text_to_html_document(
        self, text_content: str, *, metadata: Optional[dict[str, Any]] = None
    ) -> str:
        markdown = await self.markdown_processor.from_text(text_content)
        return await self.markdown_to_html_document(markdown, metadata=metadata)

    async def html_fragment_to_document(
        self, html_fragment: str, *, metadata: Optional[dict[str, Any]] = None
    ) -> str:
        return self.styles.build_html_document(html_fragment, metadata)

    # ------------------------------------------------------------------
    # Extracting from HTML documents
    # ------------------------------------------------------------------
    async def html_document_to_markdown(self, html_document: str) -> str:
        return await self.markdown_processor.from_html(html_document)

    async def html_document_to_text(self, html_document: str) -> str:
        soup = BeautifulSoup(html_document, 'html.parser')
        return soup.get_text('\n', strip=True)

    async def sanitize_html(self, html_document: str) -> str:
        """Remove script/style tags and return safe HTML."""
        soup = BeautifulSoup(html_document, 'html.parser')
        for tag in soup(['script', 'style']):
            tag.decompose()
        return str(soup)

    async def escape_text_to_html(self, text: str) -> str:
        async with self._semaphore:
            return escape(text)


__all__ = ['HTMLProcessor']
