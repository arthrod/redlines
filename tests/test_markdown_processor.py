import asyncio

from redlines.utils.markdown_processor import MarkdownProcessor


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
