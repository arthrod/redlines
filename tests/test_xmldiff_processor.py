from redlines import Redlines
from redlines.xmldiff_processor import XmlDiffProcessor


def test_xml_diff_processor_structural_metadata() -> None:
    processor = XmlDiffProcessor()
    source = '<root><p>Hello</p></root>'
    test = '<root><p>Hello <ins>there</ins></p></root>'
    processor.process(source, test)

    assert processor.structural_diff
    first_action = processor.structural_diff[0]
    assert 'action' in first_action


def test_redlines_uses_xml_processor_for_html() -> None:
    source = '<p>Hello</p>'
    test = '<p>Hello <strong>friend</strong></p>'
    diff = Redlines(source, test, source_format='html', test_format='html')

    payload = diff.output_json
    assert payload['metadata']['processor'] == 'XmlDiffProcessor'
    assert payload['metadata']['structural_diff']
