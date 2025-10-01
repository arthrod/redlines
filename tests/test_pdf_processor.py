import asyncio

import pytest

from redlines.utils import pdf_processor as pdf_module
from redlines.utils.markdown_processor import MarkdownProcessor
from redlines.utils.pdf_processor import PDFProcessor
from redlines.utils.styles import Styles


@pytest.fixture
def pdf_processor_factory(monkeypatch):
    class DummyWeasy:
        def __init__(self, string: str) -> None:
            self.string = string

        def write_pdf(self) -> bytes:
            return b'PDF-WEASY'

    class DummyStatus:
        def __init__(self, err: bool = False) -> None:
            self.err = err

    class DummyPisa:
        @staticmethod
        def CreatePDF(html_document: str, dest) -> DummyStatus:
            dest.write(b'PDF-XHTML')
            return DummyStatus()

    monkeypatch.setattr(pdf_module, 'WeasyHTML', DummyWeasy)
    monkeypatch.setattr(pdf_module, 'pisa', DummyPisa)

    def factory(**kwargs):
        return PDFProcessor(styles=Styles(), markdown_processor=MarkdownProcessor(), **kwargs)

    return factory


def test_markdown_to_pdf_prefers_weasy(pdf_processor_factory) -> None:
    processor = pdf_processor_factory()
    pdf_bytes = asyncio.run(processor.markdown_to_pdf('# Title'))
    assert pdf_bytes == b'PDF-WEASY'


def test_markdown_to_pdf_falls_back_to_xhtml(pdf_processor_factory, monkeypatch) -> None:
    processor = pdf_processor_factory()

    async def failing_weasy(self, html_document: str) -> bytes:  # noqa: ARG001 - signature required
        raise RuntimeError('backend failure')

    monkeypatch.setattr(PDFProcessor, '_render_weasyprint', failing_weasy)

    pdf_bytes = asyncio.run(processor.markdown_to_pdf('# Title', prefer_backend='weasyprint'))
    assert pdf_bytes == b'PDF-XHTML'


def test_pdf_to_markdown_error_when_extraction_missing(pdf_processor_factory, monkeypatch) -> None:
    processor = pdf_processor_factory()

    async def stub_from_pdf(payload: bytes) -> str:  # noqa: ARG001 - signature required
        return ''

    monkeypatch.setattr(processor.markdown_processor, 'from_pdf', stub_from_pdf)

    with pytest.raises(ValueError):
        asyncio.run(processor.pdf_to_markdown(b'%PDF'))


def test_pdf_to_html_uses_styles(pdf_processor_factory, monkeypatch) -> None:
    processor = pdf_processor_factory()

    async def stub_from_pdf(payload: bytes) -> str:  # noqa: ARG001
        return '# Heading\n\nContent paragraph.'

    monkeypatch.setattr(processor.markdown_processor, 'from_pdf', stub_from_pdf)

    html_output = asyncio.run(processor.pdf_to_html(b'%PDF', metadata={'title': 'Sample'}))
    assert '<html>' in html_output
    assert 'Heading' in html_output
    assert 'Content paragraph.' in html_output
