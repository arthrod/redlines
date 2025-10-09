from typer.testing import CliRunner

from redlines.cli import app

runner = CliRunner()


def test_markdown_command_outputs_markdown() -> None:
    result = runner.invoke(app, ['markdown', 'alpha', 'beta', '--style', 'none'])
    assert result.exit_code == 0
    assert '<del>' in result.stdout or '~' in result.stdout  # style none uses <del>/<ins>


def test_gallery_showcases_examples() -> None:
    result = runner.invoke(app, ['gallery'])
    assert result.exit_code == 0
    assert 'Redlines CLI' in result.stdout
    assert 'Contract tweak' in result.stdout


def test_plain_invocation_shows_overview() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert 'Getting started' in result.stdout
