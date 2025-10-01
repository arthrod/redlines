import asyncio

import pytest
from rich.text import Text

from redlines import Redlines


class StubConversionManager:
    def __init__(self) -> None:
        self.extract_calls: list[tuple[str, str | bytes]] = []
        self.convert_calls: list[tuple[str, str]] = []

    def extract_text_sync(self, data, source_format):
        self.extract_calls.append((source_format, data))
        return f'{source_format}-text'

    async def extract_text(self, data, source_format):  # pragma: no cover - invoked in async tests
        self.extract_calls.append((f'async-{source_format}', data))
        return f'async-{source_format}-text'

    def convert_sync(self, data, source_format, target_format, *, metadata=None):
        self.convert_calls.append((source_format, target_format))
        return b'converted-sync'

    async def convert(self, data, source_format, target_format, *, metadata=None):  # pragma: no cover
        self.convert_calls.append((f'async-{source_format}', target_format))
        return b'converted-async'


@pytest.mark.parametrize(
    ('test_string_1', 'test_string_2', 'expected_md'),
    [
        (
            'The quick brown fox jumps over the dog.',
            'The quick brown fox jumps over the lazy dog.',
            'The quick brown fox jumps over the <ins>lazy </ins>dog.',
        )
    ],
)
def test_redline_add_md(test_string_1, test_string_2, expected_md) -> None:
    test = Redlines(test_string_1, test_string_2, markdown_style='none')
    assert test.output_markdown == expected_md


@pytest.mark.parametrize(
    ('test_string_1', 'test_string_2', 'expected_md'),
    [
        (
            'The quick brown fox jumps over the lazy dog.',
            'The quick brown fox jumps over the dog.',
            'The quick brown fox jumps over the <del>lazy </del>dog.',
        )
    ],
)
def test_redline_delete_md(test_string_1, test_string_2, expected_md) -> None:
    test = Redlines(test_string_1, test_string_2, markdown_style='none')
    assert test.output_markdown == expected_md


@pytest.mark.parametrize(
    ('test_string_1', 'test_string_2', 'expected_md'),
    [
        (
            'The quick brown fox jumps over the lazy dog.',
            'The quick brown fox walks past the lazy dog.',
            'The quick brown fox <del>jumps over </del><ins>walks past </ins>the lazy dog.',
        )
    ],
)
def test_redline_replace_md(test_string_1, test_string_2, expected_md) -> None:
    test = Redlines(test_string_1, test_string_2, markdown_style='none')
    assert test.output_markdown == expected_md


@pytest.mark.parametrize(
    ('test_string_1', 'test_string_2', 'expected_rich'),
    [
        (
            'The quick brown fox jumps over the dog.',
            'The quick brown fox jumps over the lazy dog.',
            Text.from_markup('The quick brown fox jumps over the [green]lazy [/green]dog.'),
        )
    ],
)
def test_redline_add_rich(test_string_1, test_string_2, expected_rich) -> None:
    test = Redlines(test_string_1, test_string_2)
    assert test.output_rich == expected_rich


# @pytest.mark.skip("Not sure why [red strike] is not the same as [strike red]")
@pytest.mark.parametrize(
    ('test_string_1', 'test_string_2', 'expected_rich'),
    [
        (
            'The quick brown fox jumps over the lazy dog.',
            'The quick brown fox jumps over the dog.',
            Text.from_markup('The quick brown fox jumps over the [red strike]lazy [/red strike]dog.'),
        )
    ],
)
def test_redline_delete_rich(test_string_1, test_string_2, expected_rich) -> None:
    test = Redlines(test_string_1, test_string_2)
    assert test.output_rich == expected_rich


@pytest.mark.parametrize(
    ('test_string_1', 'test_string_2', 'expected_rich'),
    [
        (
            'The quick brown fox jumps over the lazy dog.',
            'The quick brown fox walks past the lazy dog.',
            Text.from_markup(
                'The quick brown fox [red strike]jumps over [/red strike][green]walks past [/green]the lazy dog.'
            ),
        )
    ],
)
def test_redline_replace_rich(test_string_1, test_string_2, expected_rich) -> None:
    test = Redlines(test_string_1, test_string_2)
    assert test.output_rich == expected_rich


def test_compare() -> None:
    test_string_1 = 'The quick brown fox jumps over the lazy dog.'
    test_string_2 = 'The quick brown fox walks past the lazy dog.'
    expected_md = 'The quick brown fox <del>jumps over </del><ins>walks past </ins>the lazy dog.'
    expected_rich = Text.from_markup(
        'The quick brown fox [red strike]jumps over [/red strike][green]walks past [/green]the lazy dog.'
    )
    test = Redlines(test_string_1, markdown_style='none')
    assert test.compare(test_string_2) == expected_md

    # When compare is called twice on the same test string, the first result is given
    assert test.compare(test_string_2) == expected_md

    assert (
        test.compare('The quick brown fox jumps over the dog.')
        == 'The quick brown fox jumps over the <del>lazy </del>dog.'
    )

    # Not giving the Redline object anything to test with throws an error.
    test = Redlines(test_string_1)
    with pytest.raises(ValueError):
        test.compare()

    test = Redlines(test_string_1)
    assert test.compare(test_string_2, output='rich') == expected_rich


def test_opcodes_error() -> None:
    test_string_1 = 'The quick brown fox jumps over the lazy dog.'
    redline = Redlines(test_string_1)
    with pytest.raises(ValueError):
        _ = redline.redlines


def test_source() -> None:
    test_string_1 = 'The quick brown fox jumps over the lazy dog.'
    test = Redlines(test_string_1, markdown_style='none')
    assert test.source == test_string_1


def test_markdown_style() -> None:
    # Test default - "red green"
    test_string_1 = 'The quick brown fox jumps over the lazy dog.'
    test_string_2 = 'The quick brown fox walks past the lazy dog.'
    expected_md = "The quick brown fox <span style='color:red;font-weight:700;text-decoration:line-through;'>jumps over </span><span style='color:green;font-weight:700;'>walks past </span>the lazy dog."
    test = Redlines(test_string_1)
    assert test.compare(test_string_2) == expected_md

    # Test None style
    test_string_1 = 'The quick brown fox jumps over the lazy dog.'
    test_string_2 = 'The quick brown fox walks past the lazy dog.'
    expected_md = 'The quick brown fox <del>jumps over </del><ins>walks past </ins>the lazy dog.'
    test = Redlines(test_string_1, markdown_style=None)
    assert test.compare(test_string_2) == expected_md

    # Test "none" style
    test_string_1 = 'The quick brown fox jumps over the lazy dog.'
    test_string_2 = 'The quick brown fox walks past the lazy dog.'
    expected_md = 'The quick brown fox <del>jumps over </del><ins>walks past </ins>the lazy dog.'
    test = Redlines(test_string_1, markdown_style='none')
    assert test.compare(test_string_2) == expected_md

    # Test one of the provided markdown styles
    expected_md = (
        "The quick brown fox <span style='color:red;font-weight:700;text-decoration:line-through;'>jumps "
        "over </span><span style='color:red;font-weight:700;'>walks past </span>the lazy dog."
    )
    test = Redlines(test_string_1, markdown_style='red')
    assert test.compare(test_string_2) == expected_md

    expected_md = (
        "The quick brown fox <span style='color:red;font-weight:700;text-decoration:line-through;'>jumps "
        "over </span><span style='color:blue;font-weight:700;'>walks past </span>the lazy dog."
    )
    test = Redlines(test_string_1, markdown_style='red_blue')
    assert test.compare(test_string_2) == expected_md

    # Test default custom css styles
    expected_md = (
        "The quick brown fox <span class='redline-deleted'>jumps "
        "over </span><span class='redline-inserted'>walks past </span>the lazy dog."
    )
    test = Redlines(test_string_1, markdown_style='custom_css')
    assert test.compare(test_string_2) == expected_md

    # Test custom css styles with custom names
    expected_md = (
        "The quick brown fox <span class='deleted'>jumps "
        "over </span><span class='inserted'>walks past </span>the lazy dog."
    )
    test = Redlines(test_string_1, markdown_style='custom_css', ins_class='inserted', del_class='deleted')
    assert test.compare(test_string_2) == expected_md

    # Test ghfm (GitHub Flavored Markdown) style
    expected_md = 'The quick brown fox ~~jumps over ~~**walks past **the lazy dog.'
    test = Redlines(test_string_1, markdown_style='ghfm')
    assert test.compare(test_string_2) == expected_md

    # Test bbcode (BBCode) style
    expected_md = (
        'The quick brown fox [s][color=red]jumps over [/color][/s][b][color=green]walks past [/color][/b]the lazy dog.'
    )
    test = Redlines(test_string_1, markdown_style='bbcode')
    assert test.compare(test_string_2) == expected_md

    # Test streamlit style
    expected_md = 'The quick brown fox ~~:red[jumps over ]~~ **:green[walks past ]** the lazy dog.'
    test = Redlines(test_string_1, markdown_style='streamlit')
    assert test.compare(test_string_2) == expected_md


def test_redlines_with_conversion_manager() -> None:
    manager = StubConversionManager()
    redline = Redlines(
        {'content': b'PDFDATA', 'format': 'pdf'},
        {'content': b'DOCXDATA', 'format': 'docx'},
        conversion_manager=manager,
        markdown_style='none',
    )

    assert redline.source == 'pdf-text'
    assert redline.test == 'docx-text'
    assert ('pdf', b'PDFDATA') in manager.extract_calls
    assert ('docx', b'DOCXDATA') in manager.extract_calls

    converted_sync = redline.convert('payload', 'txt', 'docx')
    assert converted_sync == b'converted-sync'
    assert ('txt', 'docx') in manager.convert_calls

    async_extract = redline.extract_text('payload', 'md', asynchronous=True)
    assert asyncio.run(async_extract) == 'async-md-text'

    async_convert = redline.convert('payload', 'txt', 'pdf', asynchronous=True)
    assert asyncio.run(async_convert) == b'converted-async'
    assert ('async-txt', 'pdf') in manager.convert_calls


def test_paragraphs_handling() -> None:
    test_string_1 = """
Happy Saturday,

Thank you for reaching out, have a good weekend

Sophia
"""
    test_string_2 = """Happy Saturday,

Thank you for reaching out. Have a good weekend.

Sophia."""
    expected_md = (
        'Happy Saturday, \n\nThank you for reaching <del>out, have </del><ins>out. Have </ins>a good '
        '<del>weekend </del><ins>weekend. </ins>\n\n<del>Sophia</del><ins>Sophia.</ins>'
    )
    test = Redlines(test_string_1, markdown_style='none')
    assert test.compare(test_string_2) == expected_md


def test_different_number_of_paragraphs() -> None:
    test_string_1 = """
Happy Saturday,

Thank you for reaching out, have a good weekend

Best,

Sophia
"""
    test_string_2 = """Happy Saturday,

Thank you for reaching out. Have a good weekend.

Sophia."""

    expected_md = (
        'Happy Saturday, \n\nThank you for reaching <del>out, have </del><ins>out. Have </ins>a good <del>weekend '
        '</del><ins>weekend. </ins>\n\n<del>Best, ¶ Sophia</del><ins>Sophia.</ins>'
    )
    test = Redlines(test_string_1, test_string_2, markdown_style='none')
    assert test.output_markdown == expected_md
