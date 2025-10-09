import asyncio

from redlines.utils.html_processor import HTMLProcessor
from redlines.utils.styles import Styles


def test_markdown_to_html_document() -> None:
    processor = HTMLProcessor(styles=Styles())
    html_document = asyncio.run(processor.markdown_to_html_document('# Title'))
    assert '<html>' in html_document
    assert 'Title' in html_document


def test_html_document_to_text() -> None:
    processor = HTMLProcessor(styles=Styles())
    html_document = '<html><body><div class="content"><p>Sample</p></div></body></html>'
    text = asyncio.run(processor.html_document_to_text(html_document))
    assert text == 'Sample'
