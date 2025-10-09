from __future__ import annotations

import asyncio
from pathlib import Path

from redlines import Redlines
from redlines.utils.conversion_manager import ConversionManager
from redlines.utils.docx_processor import DOCXProcessor


DIST_DIR = Path('dist')
DIST_DIR.mkdir(exist_ok=True)


async def build_track_changes_docx(markdown: str, output_path: Path) -> None:
    processor = DOCXProcessor()
    html_fragment = f'<div class="redlines-output">{markdown}</div>'
    docx_bytes = await processor.html_to_docx(html_fragment)
    output_path.write_bytes(docx_bytes)


def process_pair(label: str, source_path: str, target_path: str) -> None:
    manager = ConversionManager()
    source = {'content': source_path, 'format': 'docx'}
    target = {'content': target_path, 'format': 'docx'}

    diff = Redlines(
        source,
        target,
        conversion_manager=manager,
        source_format='docx',
        test_format='docx',
        markdown_style='none',
    )

    json_path = DIST_DIR / f'{label}_htmltodocx_diff.json'
    diff.to_json_file(json_path)
    print(f'[{label}] Structured diff saved to {json_path}')
    print(f"[{label}] Summary: {diff.output_json['summary']}")

    docx_path = DIST_DIR / f'{label}_htmltodocx_track_changes.docx'
    asyncio.run(build_track_changes_docx(diff.output_markdown, docx_path))
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
