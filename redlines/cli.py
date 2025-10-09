"""Redlines command line interface powered by Typer and Rich.

The CLI focuses on a delightful terminal experience while exposing the three
core output formats supported by :class:`redlines.Redlines`.  The entry point is
configured in ``pyproject.toml`` as ``redlines``.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version
from typing import Iterable

import typer
from rich import box
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from redlines import Redlines

try:
    PACKAGE_VERSION = version('redlines')
except PackageNotFoundError:  # pragma: no cover - local development fallback
    PACKAGE_VERSION = '0.0.0-dev'

app = typer.Typer(
    name='redlines',
    add_completion=False,
    help='Beautiful, track-change-inspired diffs for Markdown, Rich text, and terminal output.',
)

console = Console()


def _render_header(subtitle: str | None = None) -> None:
    banner = Text.assemble(
        ('══╡ ', 'bold red'),
        ('Redlines CLI ', 'bold magenta'),
        (f'v{PACKAGE_VERSION}', 'bold white'),
        (' ╞══', 'bold red'),
    )
    subtitle_text = subtitle or 'Compare documents with instant, gorgeous output.'
    console.print(
        Panel.fit(
            Align.center(Text(subtitle_text, justify='center')), border_style='magenta', title=banner
        ),
        justify='center',
    )


def _render_examples_table(examples: Iterable[tuple[str, str, str]]) -> Table:
    table = Table(title='✨ Redlines Gallery', box=box.ROUNDED, show_lines=False)
    table.add_column('Example', style='cyan', no_wrap=True)
    table.add_column('Source snippet', style='green')
    table.add_column('Test snippet', style='red')
    for title, src, test in examples:
        table.add_row(title, src, test)
    return table


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version_flag: bool = typer.Option(
        False,
        '--version',
        '-V',
        help='Show the redlines CLI version and exit.',
        rich_help_panel='General options',
    ),
) -> None:
    """Entry point for the CLI. Displays overview when invoked without commands."""
    if version_flag:
        console.print(f'[bold magenta]redlines[/] {PACKAGE_VERSION}', justify='center')
        raise typer.Exit()

    if ctx.invoked_subcommand is not None:
        return

    _render_header()
    overview = textwrap.dedent(
        """
        • Run `redlines text SOURCE TEST` for a rich side-by-side preview.
        • Run `redlines simple SOURCE TEST` for a minimal inline diff.
        • Run `redlines markdown SOURCE TEST --style none` to generate Markdown deltas.
        • Run `redlines gallery` to explore curated CLI examples.
        """
    ).strip()
    console.print(Panel.fit(overview, title='Getting started', border_style='cyan'), justify='center')


@app.command()
def text(
    source: str = typer.Argument(..., help='Source text to compare.'),
    test: str = typer.Argument(..., help='Test text to compare against the source.'),
    title: str = typer.Option('Rich diff canvas', help='Panel title for the rendered comparison.'),
) -> None:
    """Display a deluxe, panelled diff using Rich layouts."""
    _render_header('Live comparison canvas')
    diff = Redlines(source, test)

    layout = Layout()
    layout.split_column(
        Layout(name='banner', size=3),
        Layout(name='body'),
    )
    layout['banner'].update(
        Align.center(Text('Bring your contract reviews to the terminal. ✨', style='bold green'))
    )

    sub_layout = Layout()
    sub_layout.split_row(
        Layout(Panel.fit(source, title='Source', border_style='green')),
        Layout(Panel.fit(test, title='Test', border_style='red')),
    )

    layout['body'].split_column(
        Layout(Panel.fit(diff.output_rich, title=title, border_style='magenta')), sub_layout
    )

    console.print(layout)


@app.command('simple')
def simple_text(
    source: str = typer.Argument(..., help='Source text to compare.'),
    test: str = typer.Argument(..., help='Test text to compare against the source.'),
) -> None:
    """Print a concise Rich-formatted diff suitable for piping into other tools."""
    _render_header('Inline diff output')
    console.print(Redlines(source, test).output_rich)


@app.command()
def markdown(
    source: str = typer.Argument(..., help='Source text to compare.'),
    test: str = typer.Argument(..., help='Test text to compare against the source.'),
    style: str = typer.Option(
        'red_green',
        '--style',
        '-s',
        case_sensitive=False,
        help='Markdown diff style (red_green, red_blue, none, red, ghfm, bbcode, streamlit).',
    ),
    output_json: str | None = typer.Option(
        None,
        '--output-json',
        help='Write structured diff JSON to a file path (use "-" for stdout).',
        rich_help_panel='Output options',
    ),
) -> None:
    """Emit the comparison as Markdown, optionally using alternate styles."""
    _render_header('Markdown delta output')
    diff = Redlines(source, test, markdown_style=style)
    syntax = Syntax(diff.output_markdown, 'markdown', theme='github-dark', line_numbers=False)
    console.print(syntax)

    if output_json:
        if output_json == '-':
            console.print_json(data=diff.output_json)
        else:
            path = Path(output_json)
            diff.to_json_file(path)
            console.print(f'[dim]Structured diff written to {path}[/dim]')


@app.command()
def gallery() -> None:
    """Showcase built-in examples that highlight the CLI layout capabilities."""
    _render_header('Gallery of curated examples')
    sample_pairs = [
        (
            'Contract tweak',
            'Party A shall deliver goods within five (5) business days.',
            'Party A shall deliver goods within three (3) business days.',
        ),
        (
            'Product roadmap',
            'Our Q3 roadmap focuses on stability improvements and bug fixes.',
            'Our Q3 roadmap focuses on generative AI copilots and bug fixes.',
        ),
        (
            'Email polish',
            'Thanks for reaching out, happy to help with the rollout next week.',
            'Thanks for reaching out! Happy to support the rollout later this week.',
        ),
    ]

    table = _render_examples_table(sample_pairs)
    console.print(table)
    console.print('\nUse `redlines text` with the snippets above to explore further. 🚀', style='dim')


if __name__ == '__main__':
    app()
