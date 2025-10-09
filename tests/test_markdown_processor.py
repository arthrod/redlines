import asyncio
from io import BytesIO

import pytest

from redlines.utils.markdown_processor import MarkdownProcessor

pytest.importorskip('docx')
from docx import Document as DocxDocument  # noqa: E402


def test_markdown_roundtrip() -> None:
    processor = MarkdownProcessor()
    markdown = '# Heading\n\n* bullet'
    html = asyncio.run(processor.to_html(markdown))
    assert '<h1>Heading</h1>' in html
    text = asyncio.run(processor.to_text(markdown))
    assert 'Heading' in text


def test_markdown_from_html() -> None:
    processor = MarkdownProcessor()
    html = '<h1>Heading</h1><p>Paragraph</p>'
    markdown = asyncio.run(processor.from_html(html))
    assert '# Heading' in markdown
    assert 'Paragraph' in markdown


def test_docx_fallback_uses_python_docx() -> None:
    processor = MarkdownProcessor(enable_docling=False, enable_markitdown=False)
    document = DocxDocument()
    document.add_paragraph('Fallback Body Text')
    buffer = BytesIO()
    document.save(buffer)
    payload = buffer.getvalue()

    markdown = asyncio.run(processor.from_docx(payload))
    assert 'Fallback Body Text' in markdown
