import asyncio
import zipfile

import pytest

pytest.importorskip('docx')

from docx.oxml.ns import qn

from redlines.utils.docx_processor import DOCXProcessor
from redlines.utils.docx_track_changes import TrackChangesBuilder


def test_track_changes_builder_creates_elements() -> None:
    builder = TrackChangesBuilder(author='Tester', revision_start=5)
    insertion = builder.create_insertion('Hello')
    deletion = builder.create_deletion('Bye')

    assert insertion.tag.endswith('ins')
    assert insertion.get(qn('w:author')) == 'Tester'
    assert insertion.get(qn('w:id')) == '5'
    assert deletion.tag.endswith('del')
    assert deletion.get(qn('w:id')) == '6'


def test_html_to_docx_emits_track_changes(tmp_path) -> None:
    processor = DOCXProcessor()
    html = '<p>Hello <ins><strong>friend</strong></ins> and <del><em>foe</em></del></p>'

    docx_bytes = asyncio.run(processor.html_to_docx(html))
    docx_path = tmp_path / 'diff.docx'
    docx_path.write_bytes(docx_bytes)

    with zipfile.ZipFile(docx_path) as archive:
        document_xml = archive.read('word/document.xml').decode('utf-8')

    assert '<w:ins' in document_xml
    assert '<w:del' in document_xml

    assert '<w:b/>' in document_xml
    assert '<w:i/>' in document_xml
