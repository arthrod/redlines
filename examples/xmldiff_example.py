"""Demonstrate HTML-aware diffs powered by the XmlDiffProcessor."""

from pprint import pprint

from redlines import Redlines

source_html = """
<p>Hello <strong>world</strong>.</p>
<ul>
    <li>First item</li>
    <li>Second item</li>
</ul>
"""

test_html = """
<p>Hello <em>world</em>!</p>
<ul>
    <li>First item</li>
    <li><ins>Brand new item</ins></li>
</ul>
"""

diff = Redlines(
    source_html,
    test_html,
    source_format='html',
    test_format='html',
    markdown_style='red_blue',
)

print('Markdown diff:')
print(diff.output_markdown)
print('\nStructured JSON diff:')
pprint(diff.output_json)
