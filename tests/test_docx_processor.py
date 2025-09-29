import asyncio
from io import BytesIO

import pytest

from redlines.utils.docx_processor import DOCXProcessor, DocxProcessingMethod
from redlines.utils.markdown_processor import MarkdownProcessor
from redlines.utils.styles import Styles

pytest.importorskip('docx')
from docx import Document as DocxDocument  # noqa: E402  (import after skip)


def test_manual_markdown_to_docx_conversion() -> None:
    processor = DOCXProcessor(
        styles=Styles(),
        markdown_processor=MarkdownProcessor(),
        html4docx_enabled=False,
        manual_enabled=True,
        preferred_method=DocxProcessingMethod.MANUAL,
    )
    docx_bytes = asyncio.run(processor.markdown_to_docx('# Title\n\nParagraph', method=DocxProcessingMethod.MANUAL))
    document = DocxDocument(BytesIO(docx_bytes))
    assert document.paragraphs[0].text == 'Title'
    assert 'Paragraph' in document.paragraphs[1].text
