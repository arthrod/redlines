from dataclasses import dataclass

import pytest

from redlines.utils.conversion_manager import ConversionManager
from redlines.utils.html_processor import HTMLProcessor
from redlines.utils.markdown_processor import MarkdownProcessor
from redlines.utils.styles import Styles


@dataclass
class StubDocxProcessor:
    calls: list

    async def docx_to_markdown(self, payload: bytes) -> str:
        self.calls.append(('docx_to_markdown', payload))
        return 'docx-markdown'

    async def markdown_to_docx(self, markdown: str, *, method=None) -> bytes:  # noqa: ARG002 - method unused
        self.calls.append(('markdown_to_docx', markdown))
        return f'DOCX:{markdown}'.encode('utf-8')


@dataclass
class StubPDFProcessor:
    calls: list

    async def pdf_to_markdown(self, payload: bytes) -> str:
        self.calls.append(('pdf_to_markdown', payload))
        return 'pdf-markdown'

    async def markdown_to_pdf(self, markdown: str, *, metadata=None, prefer_backend=None) -> bytes:  # noqa: ARG002
        self.calls.append(('markdown_to_pdf', markdown))
        return f'PDF:{markdown}'.encode('utf-8')


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
        ('docx', 'md', b'DOCXDATA', str, 'docx-markdown'),
        ('pdf', 'md', b'PDFDATA', str, 'pdf-markdown'),
        ('md', 'pdf', '# Heading', bytes, b'PDF:'),
        ('html', 'docx', '<p>Paragraph</p>', bytes, b'DOCX:'),
        ('docx', 'html', b'DOCXDATA', str, 'docx-markdown'),
        ('html', 'pdf', '<p>Paragraph</p>', bytes, b'PDF:'),
        ('pdf', 'html', b'PDFDATA', str, 'pdf-markdown'),
        ('txt', 'pdf', 'Plain text', bytes, b'PDF:'),
        ('pdf', 'txt', b'PDFDATA', str, 'pdf-markdown'),
        ('docx', 'txt', b'DOCXDATA', str, 'docx-markdown'),
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
        assert any(call[0] == 'docx_to_markdown' for call in docx_stub.calls)
    if source_format == 'pdf':
        assert any(call[0] == 'pdf_to_markdown' for call in pdf_stub.calls)


@pytest.mark.parametrize(
    ('source_format', 'payload', 'expected_text'),
    [
        ('docx', b'DOCXDATA', 'docx-markdown'),
        ('pdf', b'PDFDATA', 'pdf-markdown'),
        ('md', '# Heading', 'Heading'),
        ('txt', 'Plain text', 'Plain text'),
        ('html', '<p>Paragraph</p>', 'Paragraph'),
    ],
)
def test_extract_text_sync(managed_conversion, source_format, payload, expected_text):
    manager, _, _ = managed_conversion
    text = manager.extract_text_sync(payload, source_format)
    assert expected_text in text
