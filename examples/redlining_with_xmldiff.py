from __future__ import annotations

import lxml.etree as ET
from bs4 import BeautifulSoup
from pathlib import Path
from xmldiff import formatting, main as xmldiff_main

from redlines.utils.conversion_manager import ConversionManager

TEXT_TAGS = ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li')
FORMAT_TAGS = (
    'b',
    'strong',
    'i',
    'em',
    'u',
    'strike',
    's',
    'del',
    'ins',
    'span',
    'a',
    'sup',
    'sub',
)

XSLT = ET.XML(
    '''<?xml version="1.0"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:diff="http://namespaces.shoobx.com/diff">

    <!-- Handle diff:delete elements -->
    <xsl:template match="diff:delete">
        <del><xsl:apply-templates/></del>
    </xsl:template>

    <!-- Handle diff:insert elements -->
    <xsl:template match="diff:insert">
        <ins><xsl:apply-templates/></ins>
    </xsl:template>

    <!-- Handle elements with @diff:delete attribute -->
    <xsl:template match="*[@diff:delete]">
        <del>
            <xsl:element name="{local-name()}">
                <xsl:apply-templates select="@*[not(namespace-uri()='http://namespaces.shoobx.com/diff')] | node()"/>
            </xsl:element>
        </del>
    </xsl:template>

    <!-- Handle elements with @diff:insert attribute -->
    <xsl:template match="*[@diff:insert]">
        <ins>
            <xsl:element name="{local-name()}">
                <xsl:apply-templates select="@*[not(namespace-uri()='http://namespaces.shoobx.com/diff')] | node()"/>
            </xsl:element>
        </ins>
    </xsl:template>

    <xsl:template match="@diff:insert-formatting">
        <xsl:attribute name="class">insert-formatting</xsl:attribute>
    </xsl:template>

    <!-- Copy everything else, but strip diff namespace attributes -->
    <xsl:template match="@* | node()">
      <xsl:copy>
        <xsl:apply-templates select="@*[not(namespace-uri()='http://namespaces.shoobx.com/diff')] | node()"/>
      </xsl:copy>
    </xsl:template>
</xsl:stylesheet>
'''
)


class StyledHTMLFormatter(formatting.XMLFormatter):
    """Formatter that maps xmldiff metadata to HTML elements."""

    def __init__(self) -> None:
        super().__init__(text_tags=TEXT_TAGS, formatting_tags=FORMAT_TAGS, normalize=formatting.WS_BOTH)
        self._transform = ET.XSLT(XSLT)

    def render(self, result):  # type: ignore[override]
        transformed = self._transform(result)
        return super().render(transformed)


def convert_docx_to_html(path: str, manager: ConversionManager) -> str:
    html_doc = manager.convert_sync(path, 'docx', 'html')
    soup = BeautifulSoup(html_doc, 'html.parser')
    return str(soup)


def process_pair(label: str, source_path: str, target_path: str) -> None:
    manager = ConversionManager()
    left_html = convert_docx_to_html(source_path, manager)
    right_html = convert_docx_to_html(target_path, manager)

    formatter = StyledHTMLFormatter()
    rendered_html = xmldiff_main.diff_texts(left_html, right_html, formatter=formatter)

    raw_actions = xmldiff_main.diff_texts(left_html, right_html)

    output_dir = Path('dist')
    output_dir.mkdir(exist_ok=True)

    html_path = output_dir / f'{label}_xmldiff_diff.html'
    html_path.write_text(rendered_html, encoding='utf-8')
    print(f'[{label}] xmldiff HTML diff saved to {html_path}')

    actions_path = output_dir / f'{label}_xmldiff_actions.txt'
    actions_path.write_text('\n'.join(map(str, raw_actions)), encoding='utf-8')
    print(f'[{label}] xmldiff actions saved to {actions_path}\n')

    # Generate docx with tracked changes
    docx_path = output_dir / f'{label}_xmldiff_track_changes.docx'
    docx_bytes = manager._run_sync(manager.docx_processor.html_to_docx(rendered_html))
    docx_path.write_bytes(docx_bytes)
    print(f'[{label}] Track-changes DOCX written to {docx_path}\n')


def main() -> None:
    pairs = [
        ('batch1', 'tests/documents/PlainTextFile/forredlinetest_a.docx', 'tests/documents/PlainTextFile/forredlinetest_b.docx'),
        ('batch2', 'tests/documents/PlainTextFile/forredlinetest_a_two.docx', 'tests/documents/PlainTextFile/forredlinetest_b_two.docx'),
    ]

    for label, src, dst in pairs:
        process_pair(label, src, dst)


if __name__ == '__main__':
    main()
