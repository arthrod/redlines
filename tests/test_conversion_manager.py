from dataclasses import dataclass
from typing import Any, List, Optional, Tuple, Union

import pytest

from redlines.utils.conversion_manager import ConversionManager
from redlines.utils.html_processor import HTMLProcessor
from redlines.utils.markdown_processor import MarkdownProcessor
from redlines.utils.styles import Styles


@dataclass
class StubDocxProcessor:
    calls: List[Tuple[str, Union[bytes, str]]]

    async def docx_to_html(self, payload: bytes) -> str:
        self.calls.append(('docx_to_html', payload))
        return '<p>docx-html</p>'

    async def html_to_docx(self, html_content: str, *, method=None) -> bytes:
        self.calls.append(('html_to_docx', html_content))
        return f'DOCX:{html_content}'.encode('utf-8')

    async def markdown_to_docx(self, markdown_content: str, *, method=None) -> bytes:
        self.calls.append(('markdown_to_docx', markdown_content))
        return f'DOCX:{markdown_content}'.encode('utf-8')

    async def text_to_docx(self, text_content: str, *, method=None) -> bytes:
        self.calls.append(('text_to_docx', text_content))
        return f'DOCX:{text_content}'.encode('utf-8')

    async def docx_to_markdown(self, payload: bytes) -> str:
        self.calls.append(('docx_to_markdown', payload))
        return '<p>docx-markdown</p>'

    async def docx_to_text(self, payload: bytes) -> str:
        self.calls.append(('docx_to_text', payload))
        return '<p>docx-text</p>'


from redlines.utils.pdf_processor import PDFProcessor


@dataclass
class StubPDFProcessor(PDFProcessor):
    calls: List[Tuple[str, Union[bytes, str]]]

    async def pdf_to_html(self, payload: bytes, *, metadata: Optional[dict[str, Any]] = None) -> str:
        self.calls.append(('pdf_to_html', payload))
        return '<p>pdf-html</p>'

    async def html_to_pdf(
        self, html_content: str, *, metadata=None, treat_as_fragment=True, prefer_backend=None
    ) -> bytes:
        self.calls.append(('html_to_pdf', html_content))
        return f'PDF:{html_content}'.encode('utf-8')


@pytest.fixture
def managed_conversion() -> tuple[ConversionManager, StubDocxProcessor, StubPDFProcessor]:
    styles = Styles()
    markdown_processor = MarkdownProcessor()
    docx_stub = StubDocxProcessor(calls=[])
    pdf_stub = StubPDFProcessor(calls=[])
    html_processor = HTMLProcessor(styles=styles, markdown_processor=markdown_processor)

    manager = ConversionManager(
        styles=styles,
        markdown_processor=markdown_processor,
        docx_processor=docx_stub,
        pdf_processor=pdf_stub,
        html_processor=html_processor,
    )
    return manager, docx_stub, pdf_stub


@pytest.mark.parametrize(
    ('source_format', 'target_format', 'payload', 'expected_type', 'expected_marker'),
    [
        ('pdf', 'docx', b'PDFDATA', bytes, b'DOCX:'),
        ('docx', 'pdf', b'DOCXDATA', bytes, b'PDF:'),
        ('docx', 'docx', b'DOCXDATA', bytes, b'DOCX:'),
        ('pdf', 'pdf', b'PDFDATA', bytes, b'PDF:'),
        ('md', 'docx', '# Heading', bytes, b'DOCX:'),
        ('docx', 'md', b'DOCXDATA', str, 'docx-html'),
        ('pdf', 'md', b'PDFDATA', str, 'pdf-html'),
        ('md', 'pdf', '# Heading', bytes, b'PDF:'),
        ('html', 'docx', '<p>Paragraph</p>', bytes, b'DOCX:'),
        ('docx', 'html', b'DOCXDATA', str, 'docx-html'),
        ('html', 'pdf', '<p>Paragraph</p>', bytes, b'PDF:'),
        ('pdf', 'html', b'PDFDATA', str, 'pdf-html'),
        ('txt', 'pdf', 'Plain text', bytes, b'PDF:'),
        ('pdf', 'txt', b'PDFDATA', str, 'pdf-html'),
        ('docx', 'txt', b'DOCXDATA', str, 'docx-html'),
        ('txt', 'docx', 'Plain text', bytes, b'DOCX:'),
    ],
)
def test_conversion_paths(managed_conversion, source_format, target_format, payload, expected_type, expected_marker):
    manager, docx_stub, pdf_stub = managed_conversion
    result = manager.convert_sync(payload, source_format, target_format)

    assert isinstance(result, expected_type)
    if isinstance(result, bytes):
        assert result.startswith(expected_marker)
    else:
        assert expected_marker in result

    if source_format == 'docx':
        assert any(call[0] == 'docx_to_html' for call in docx_stub.calls)
    if source_format == 'pdf':
        assert any(call[0] == 'pdf_to_html' for call in pdf_stub.calls)


@pytest.mark.parametrize(
    ('source_format', 'payload', 'expected_text'),
    [
        ('docx', b'DOCXDATA', 'docx-html'),
        ('pdf', b'PDFDATA', 'pdf-html'),
        ('md', '# Heading', 'Heading'),
        ('txt', 'Plain text', 'Plain text'),
        ('html', '<p>Paragraph</p>', 'Paragraph'),
    ],
)
def test_extract_text_sync(managed_conversion, source_format, payload, expected_text):
    manager, _, _ = managed_conversion
    text = manager.extract_text_sync(payload, source_format)
    assert expected_text in text
