import pytest

pytest.importorskip('docx')
from docx import Document  # noqa: E402

from redlines.utils.styles import Styles


def test_styles_update_and_build_html() -> None:
    styles = Styles()
    styles.update({'font': {'name': 'Arial', 'size': 10}})
    html = styles.build_html_document('<p>Hello</p>', metadata={'title': 'Sample'})
    assert 'Arial' in html
    assert 'Hello' in html


def test_styles_apply_paragraph_defaults() -> None:
    document = Document()
    paragraph = document.add_paragraph('Sample text')
    styles = Styles({'font': {'name': 'Calibri', 'size': 11}})
    styles.apply_paragraph_defaults(paragraph)
    run = paragraph.runs[0]
    assert run.font.name == 'Calibri'
