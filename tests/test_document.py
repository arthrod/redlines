from redlines import Redlines


def test_PlainTextFile_text() -> None:
    from redlines import PlainTextFile

    source = PlainTextFile('tests/documents/PlainTextFile/source.txt')
    assert source.text == 'The quick brown fox jumps over the lazy dog.'

    test = PlainTextFile('tests/documents/PlainTextFile/test.txt')
    assert test.text == 'The quick brown fox walks past the lazy dog.'

    redline = Redlines(source, test)
    assert (
        redline.output_markdown
        == "The quick brown fox ~~jumps~~**walks** ~~over~~**past** the lazy dog."
    )
