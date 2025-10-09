import pytest

from redlines import Redlines


def test_output_json_basic_counts() -> None:
    diff = Redlines('alpha beta', 'alpha brave beta', markdown_style='red_blue')
    payload = diff.output_json

    assert payload['summary']['insertions'] == 1
    assert payload['summary']['total_changes'] >= 1
    assert payload['metadata']['style'] == 'red_blue'
    assert payload['metadata']['palette']['insert'] == '#1d4ed8'
    assert payload['changes'][0]['type'] in {'equal', 'insert', 'delete', 'replace'}


def test_output_json_structural_diff_for_html() -> None:
    source = '<p>Hello world</p>'
    test = '<p>Hello <ins>brave</ins> world</p>'
    diff = Redlines(source, test, source_format='html', test_format='html')
    payload = diff.output_json

    assert payload['metadata']['structural_diff']
    assert any(change['type'] == 'insert' for change in payload['changes'])


@pytest.mark.parametrize('output', ['markdown', 'rich', 'json'])
def test_compare_supports_json(output: str) -> None:
    diff = Redlines('cat', 'cats')
    result = diff.compare(output=output)
    if output == 'json':
        assert isinstance(result, dict)
        assert result['summary']['total_changes'] >= 1
        assert any(change['type'] in {'insert', 'replace'} for change in result['changes'])
    elif output == 'rich':
        from rich.text import Text

        assert isinstance(result, Text)
    else:
        assert isinstance(result, str)
