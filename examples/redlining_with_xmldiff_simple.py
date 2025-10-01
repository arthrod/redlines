from __future__ import annotations

import lxml.etree as ET
from pathlib import Path
from xmldiff import formatting, main as xmldiff_main

from redlines.utils.conversion_manager import ConversionManager

DIFF_NS = "http://namespaces.shoobx.com/diff"

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

# XSLT for transforming diff namespace to standard HTML
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


def convert_docx_to_html(path: str, manager: ConversionManager) -> str:
    html_doc = manager.convert_sync(path, 'docx', 'html')
    # Parse and reserialize to ensure well-formed XML for xmldiff
    parser = ET.HTMLParser()
    tree = ET.fromstring(html_doc.encode('utf-8'), parser)
    return ET.tostring(tree, encoding='unicode', method='xml')


def transform_diff_to_html_xslt(tree):
    """Transform diff namespace using XSLT."""
    transform = ET.XSLT(XSLT)
    result = transform(tree)
    return result


def process_pair(label: str, source_path: str, target_path: str) -> None:
    manager = ConversionManager()
    left_html = convert_docx_to_html(source_path, manager)
    right_html = convert_docx_to_html(target_path, manager)

    # Use XMLFormatter with text_tags and formatting_tags (no XSLT)
    formatter = formatting.XMLFormatter(
        text_tags=TEXT_TAGS,
        formatting_tags=FORMAT_TAGS,
        normalize=formatting.WS_BOTH
    )

    # Get the diff - this will have diff: namespace elements/attributes
    rendered_html = xmldiff_main.diff_texts(left_html, right_html, formatter=formatter)

    # Get raw actions for reference
    raw_actions = xmldiff_main.diff_texts(left_html, right_html)

    output_dir = Path('dist')
    output_dir.mkdir(exist_ok=True)

    # Save the raw xmldiff output with namespace attributes
    raw_html_path = output_dir / f'{label}_xmldiff_simple_raw.html'
    raw_html_path.write_text(rendered_html, encoding='utf-8')
    print(f'[{label}] Raw xmldiff HTML (with diff: attrs) saved to {raw_html_path}')

    # Parse the HTML string to an lxml tree for transformation
    # Use XMLParser to preserve namespaces
    parser = ET.XMLParser()
    tree = ET.fromstring(rendered_html.encode('utf-8'), parser)

    # Transform diff namespace using XSLT
    transformed_tree = transform_diff_to_html_xslt(tree)

    # Convert back to string
    cleaned_html = ET.tostring(transformed_tree, encoding='unicode', method='html')

    # Save the cleaned HTML
    clean_html_path = output_dir / f'{label}_xmldiff_simple_clean.html'
    clean_html_path.write_text(cleaned_html, encoding='utf-8')
    print(f'[{label}] Cleaned HTML diff saved to {clean_html_path}')

    # Save actions
    actions_path = output_dir / f'{label}_xmldiff_simple_actions.txt'
    actions_path.write_text('\n'.join(map(str, raw_actions)), encoding='utf-8')
    print(f'[{label}] xmldiff actions saved to {actions_path}')

    # Generate docx with tracked changes from cleaned HTML
    docx_path = output_dir / f'{label}_xmldiff_simple_track_changes.docx'
    docx_bytes = manager._run_sync(manager.docx_processor.html_to_docx(cleaned_html))
    docx_path.write_bytes(docx_bytes)
    print(f'[{label}] Track-changes DOCX (simple method) written to {docx_path}\n')


def main() -> None:
    pairs = [
        ('batch1', 'tests/documents/PlainTextFile/forredlinetest_a.docx', 'tests/documents/PlainTextFile/forredlinetest_b.docx'),
        ('batch2', 'tests/documents/PlainTextFile/forredlinetest_a_two.docx', 'tests/documents/PlainTextFile/forredlinetest_b_two.docx'),
    ]

    for label, src, dst in pairs:
        process_pair(label, src, dst)


if __name__ == '__main__':
    main()
