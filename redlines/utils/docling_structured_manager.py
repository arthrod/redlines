from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Any, Optional

from docling.document_converter import DocumentConverter
from docling_core.types.io import DocumentStream

from .conversion_manager import ConversionManager, Format


class DoclingStructuredConversionManager(ConversionManager):
    """Conversion manager that pivots through Docling's structured representation."""

    def __init__(
        self,
        *,
        styles=None,
        docx_method=None,
        max_concurrent_operations: int = 6,
        markdown_processor=None,
        docx_processor=None,
        pdf_processor=None,
        html_processor=None,
        converter: Optional[DocumentConverter] = None,
    ) -> None:
        super().__init__(
            styles=styles,
            docx_method=docx_method,
            max_concurrent_operations=max_concurrent_operations,
            markdown_processor=markdown_processor,
            docx_processor=docx_processor,
            pdf_processor=pdf_processor,
            html_processor=html_processor,
        )
        self._converter = converter or DocumentConverter()

    async def _to_html_document(self, data: Any, fmt: Format) -> str:
        if fmt is Format.DOCX:
            payload = self._ensure_bytes(data, fmt)
            stream = DocumentStream(name='document.docx', stream=BytesIO(payload))
            conversion = await asyncio.to_thread(self._converter.convert, stream)
            doc = getattr(conversion, 'document', conversion)
            html_document = doc.export_to_html()
            sanitized = await self.html_processor.sanitize_html(html_document)
            sanitized = self._strip_leading_placeholders(sanitized)
            if '<html' in sanitized.lower():
                return sanitized
            return await self.html_processor.html_fragment_to_document(sanitized)
        return await super()._to_html_document(data, fmt)

    async def convert(
        self,
        data: Any,
        source_format: str,
        target_format: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Any:
        return await super().convert(data, source_format, target_format, metadata=metadata)
