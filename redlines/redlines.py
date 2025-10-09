from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional, Tuple

from importlib.metadata import PackageNotFoundError, version

from rich.text import Text

from .document import Document
from .models import DiffChange, DiffMetadata, DiffResult, DiffSegment, DiffSummary
from .processor import Redline, WholeDocumentProcessor
from .utils.conversion_manager import ConversionManager
from .utils.styles import Styles
from .xmldiff_processor import XmlDiffProcessor


class Redlines:
    _source: str = None
    _test: str = None
    _seq1: list[str] = None
    _seq2: list[str] = None

    @property
    def source(self) -> str:
        """:return: The source text to be used as a basis for comparison."""
        return self._source

    @source.setter
    def source(self, value: Any) -> None:
        content, fmt_hint, metadata = self._unpack_input(
            value, self._pending_source_format, self._pending_source_metadata
        )
        self._source_format = fmt_hint
        self._source_metadata = metadata
        self._source = self._coerce_to_text(content, fmt_hint)
        self._pending_source_format = None
        self._pending_source_metadata = None

        self._redlines = None
        if self._test is not None:
            self._compute_redlines()

    @property
    def test(self):
        """:return: The text to be compared with the source."""
        return self._test

    @test.setter
    def test(self, value: Any) -> None:
        content, fmt_hint, metadata = self._unpack_input(value, self._pending_test_format, self._pending_test_metadata)
        self._test_format = fmt_hint
        self._test_metadata = metadata
        self._test = self._coerce_to_text(content, fmt_hint)
        self._pending_test_format = None
        self._pending_test_metadata = None

        self._redlines = None
        if self._source is not None and self._test is not None:
            self._compute_redlines()

    @property
    def redlines(self) -> list[Redline]:
        """Return the list of Redline objects representing the changes from source to test.

        :return: List of Redline objects
        """
        if self._redlines is None:
            msg = 'No test string was provided when the function was called, or during initialisation.'
            raise ValueError(msg)
        return self._redlines

    def __init__(self, source: Any, test: Any | None = None, **options) -> None:
        """Redline is a class used to compare text, and producing human-readable differences or deltas
        which look like track changes in Microsoft Word.

        ```python
        # import the class
        from redlines import Redlines

        # Create a Redlines object using the two strings to compare
        test = Redlines('The quick brown fox jumps over the lazy dog.', 'The quick brown fox walks past the lazy dog.')

        # This produces an output in Markdown format
        test.output_markdown
        ```

        Besides strings, Redlines can also receive an input in another format if it is supported by the Document class

        ```python
        from redlines import PlainTextFile

        source = PlainTextFile('tests/documents/PlainTextFile/source.txt')
        test = PlainTextFile('tests/documents/PlainTextFile/test.txt')

        redline = Redlines(source, test)
        assert (
            redline.output_markdown
            == "The quick brown fox <span style='color:red;font-weight:700;text-decoration:line-through;'>jumps over </span><span style='color:green;font-weight:700;'>walks past </span>the lazy dog."
        )
        ```

        :param source: The source text to be used as a basis for comparison.
        :param test: Optional test text to compare with the source.
        """
        self.processor: WholeDocumentProcessor | XmlDiffProcessor = WholeDocumentProcessor()
        self._html_processor: Optional[XmlDiffProcessor] = None
        self._structural_diff: list[dict[str, Any]] = []

        styles_option = options.pop('styles', None)
        conversion_manager = options.pop('conversion_manager', None)
        source_format = options.pop('source_format', None)
        test_format = options.pop('test_format', None)
        source_metadata = options.pop('source_metadata', None)
        test_metadata = options.pop('test_metadata', None)
        conversion_metadata = options.pop('conversion_metadata', None)

        if conversion_metadata:
            source_metadata = conversion_metadata.get('source', source_metadata)
            test_metadata = conversion_metadata.get('test', test_metadata)

        self.styles = self._build_styles(styles_option)
        self.conversion_manager: ConversionManager | None = conversion_manager

        self._source: Optional[str] = None
        self._test: Optional[str] = None
        self._redlines: Optional[list[Redline]] = None

        self._source_format: Optional[str] = None
        self._test_format: Optional[str] = None
        self._source_metadata: Optional[dict[str, Any]] = source_metadata
        self._test_metadata: Optional[dict[str, Any]] = test_metadata
        self._pending_source_format: Optional[str] = source_format
        self._pending_test_format: Optional[str] = test_format
        self._pending_source_metadata: Optional[dict[str, Any]] = source_metadata
        self._pending_test_metadata: Optional[dict[str, Any]] = test_metadata

        self.options = options

        self.source = source
        if test is not None:
            self.test = test

    @property
    def opcodes(self) -> list[tuple[str, int, int, int, int]]:
        """Return list of 5-tuples describing how to turn `source` into `test`.
        Similar to [`SequenceMatcher.get_opcodes`](https://docs.python.org/3/library/difflib.html#difflib.SequenceMatcher.get_opcodes).

        ```pycon
        >>> test_string_1 = 'The quick brown fox jumps over the lazy dog.'
        ... test_string_2 = 'The quick brown fox walks past the lazy dog.'
        ... s = Redlines(test_string_1, test_string_2)
        ... s.opcodes
        [('equal', 0, 4, 0, 4), ('replace', 4, 6, 4, 6), ('equal', 6, 9, 6, 9)]
        ```
        """
        return [redline.opcodes for redline in self.redlines]

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------
    def set_source(self, value: Any, *, fmt: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> None:
        """Assign a new source value along with optional format and metadata hints."""
        self._pending_source_format = fmt
        self._pending_source_metadata = metadata
        self.source = value

    def set_test(self, value: Any, *, fmt: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> None:
        """Assign a new test value along with optional format and metadata hints."""
        self._pending_test_format = fmt
        self._pending_test_metadata = metadata
        self.test = value

    def convert(
        self,
        data: Any,
        source_format: str,
        target_format: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
        asynchronous: bool = False,
    ) -> Any:
        """Convert ``data`` between formats using the shared :class:`ConversionManager`."""
        manager = self._get_conversion_manager()
        if asynchronous:
            return manager.convert(data, source_format, target_format, metadata=metadata)
        return manager.convert_sync(data, source_format, target_format, metadata=metadata)

    def extract_text(self, data: Any, source_format: str, *, asynchronous: bool = False) -> Any:
        """Extract plain text from ``data`` in ``source_format`` via the manager."""
        manager = self._get_conversion_manager()
        if asynchronous:
            return manager.extract_text(data, source_format)
        return manager.extract_text_sync(data, source_format)

    def _apply_markdown_styles(self, text: str, style: dict[str, Any]) -> str:
        if not style:
            return text

        if style.get('font-weight') == 'bold':
            text = f'**{text}**'
        if style.get('font-style') == 'italic':
            text = f'*{text}*'
        if style.get('text-decoration') == 'underline':
            # Markdown doesn't have a standard underline syntax, so we use HTML `<u>` tag.
            text = f'<u>{text}</u>'

        return text

    def _render_content(
        self,
        tokens: list[str],
        styles: Optional[list[Optional[dict[str, Any]]]],
        is_html_style: bool,
        wrapper: tuple[str, str] = ('', ''),
    ) -> str:
        if not tokens:
            return ''

        content = ""
        if styles:
            for token, style in zip(tokens, styles):
                if is_html_style:
                    safe_token = token.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    if style:
                        style_str = '; '.join(f'{k}: {v}' for k, v in style.items())
                        content += f'<span style="{style_str}">{safe_token}</span>'
                    else:
                        content += safe_token
                else:
                    if style:
                        content += self._apply_markdown_styles(token, style)
                    else:
                        content += token
        else:
            content = "".join(tokens)

        if not content:
            return ''

        return f'{wrapper[0]}{content}{wrapper[1]}'

    @property
    def output_markdown(self) -> str:
        result = []
        style = self.options.get('markdown_style', 'ghfm')
        is_html_style = style not in ['ghfm', 'bbcode', 'streamlit', 'none']

        md_styles = {}
        if style == 'none' or style is None:
            md_styles = {'ins': ('<ins>', '</ins>'), 'del': ('<del>', '</del>')}
        elif style in ('red-green', 'red_green'):
            md_styles = {'ins': ('**', '**'), 'del': ('~~', '~~')}
        elif style == 'red':
            md_styles = {'ins': ('**', '**'), 'del': ('~~', '~~')}
        elif style in {'red-blue', 'red_blue'}:
            md_styles = {'ins': ('**', '**'), 'del': ('~~', '~~')}
        elif style == 'custom_css':
            ins_class = self.options.get('ins_class', 'redline-inserted')
            del_class = self.options.get('del_class', 'redline-deleted')
            md_styles = {
                'ins': (f'<span class="{ins_class}">', '</span>'),
                'del': (f'<span class="{del_class}">', '</span>'),
            }
        elif style == 'ghfm':
            md_styles = {'ins': ('**', '**'), 'del': ('~~', '~~')}
        elif style == 'bbcode':
            md_styles = {'ins': ('[b][color=green]', '[/color][/b]'), 'del': ('[s][color=red]', '[/color][/s]')}
        elif style == 'streamlit':
            md_styles = {'ins': ('**:green[', ']**'), 'del': ('~~:red[', ']~~')}

        for redline in self.redlines:
            tag, i1, i2, j1, j2 = redline.opcodes
            source_chunk = redline.source_chunk
            test_chunk = redline.test_chunk

            if tag == 'equal':
                tokens = source_chunk.text[i1:i2]
                styles = source_chunk.slice_styles(i1, i2)
                result.append(self._render_content(tokens, styles, is_html_style))
            elif tag == 'insert':
                tokens = test_chunk.text[j1:j2]
                styles = test_chunk.slice_styles(j1, j2)
                result.append(self._render_content(tokens, styles, is_html_style, md_styles.get('ins', ('', ''))))
            elif tag == 'delete':
                tokens = source_chunk.text[i1:i2]
                styles = source_chunk.slice_styles(i1, i2)
                result.append(self._render_content(tokens, styles, is_html_style, md_styles.get('del', ('', ''))))
            elif tag == 'replace':
                del_tokens = source_chunk.text[i1:i2]
                del_styles = source_chunk.slice_styles(i1, i2)
                result.append(self._render_content(del_tokens, del_styles, is_html_style, md_styles.get('del', ('', ''))))

                ins_tokens = test_chunk.text[j1:j2]
                ins_styles = test_chunk.slice_styles(j1, j2)
                result.append(self._render_content(ins_tokens, ins_styles, is_html_style, md_styles.get('ins', ('', ''))))

        raw_output = ''.join(result)
        # Regex to find the paragraph marker with optional surrounding whitespace
        # and replace it with two newlines.
        output = re.sub(r'\s*¶\s*', '\n\n', raw_output)
        return output.strip()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _unpack_input(
        self, value: Any, default_format: Optional[str], default_metadata: Optional[dict[str, Any]]
    ) -> Tuple[Any, Optional[str], Optional[dict[str, Any]]]:
        """Normalise user input into ``(content, format_hint, metadata)``."""
        fmt_hint = default_format
        metadata = default_metadata
        content = value

        if isinstance(value, dict):
            content = value.get('content', value.get('data'))
            fmt_hint = value.get('format', fmt_hint)
            metadata = value.get('metadata', metadata)
        elif isinstance(value, tuple):
            if len(value) == 2:
                content, fmt_hint = value
            elif len(value) == 3:
                content, fmt_hint, metadata = value
            else:
                msg = 'Input tuples must have length 2 or 3 (content, format, [metadata]).'
                raise ValueError(msg)

        if content is None:
            msg = 'Input content cannot be None.'
            raise ValueError(msg)

        return content, fmt_hint, metadata

    def _coerce_to_text(self, value: Any, fmt_hint: Optional[str]) -> str:
        """Return textual content for ``value``, leveraging converters when required."""
        if isinstance(value, Document):
            return value.text
        if fmt_hint:
            return self._get_conversion_manager().extract_text_sync(value, fmt_hint)
        if isinstance(value, bytes):
            return self._decode_bytes(value)
        return str(value)

    @staticmethod
    def _decode_bytes(payload: bytes) -> str:
        try:
            return payload.decode('utf-8')
        except UnicodeDecodeError:
            return payload.decode('latin1', errors='replace')

    def _compute_redlines(self) -> None:
        if self._source is None or self._test is None:
            return

        self._select_processor()
        self._redlines = self.processor.process(self._source, self._test)
        if isinstance(self.processor, XmlDiffProcessor):
            self._structural_diff = self.processor.structural_diff
        else:
            self._structural_diff = []

    def _select_processor(self) -> None:
        if self._should_use_html_processor():
            if self._html_processor is None:
                self._html_processor = XmlDiffProcessor()
            self.processor = self._html_processor
        else:
            if not isinstance(self.processor, WholeDocumentProcessor):
                self.processor = WholeDocumentProcessor()

    def _should_use_html_processor(self) -> bool:
        fmt_hints = {self._source_format, self._test_format}
        if any(hint and 'html' in hint.lower() for hint in fmt_hints if hint):
            return True
        source_html = self._source and self._looks_like_html(self._source)
        test_html = self._test and self._looks_like_html(self._test)
        return bool(source_html or test_html)

    @staticmethod
    def _looks_like_html(value: str) -> bool:
        stripped = value.strip()
        if '<' not in stripped or '>' not in stripped:
            return False
        return stripped.startswith('<') or '</' in stripped

    @staticmethod
    def _resolve_library_version() -> str:
        try:
            return version('redlines')
        except PackageNotFoundError:  # pragma: no cover - local development fallback
            return '0.0.0-dev'

    @staticmethod
    def _build_styles(option: Any) -> Styles:
        """Construct a :class:`Styles` instance from user input."""
        if isinstance(option, Styles):
            return option
        if isinstance(option, dict):
            return Styles(config=option)
        if option is None:
            return Styles()
        msg = 'styles must be a Styles instance, a dict configuration, or None'
        raise TypeError(msg)

    def _get_conversion_manager(self) -> ConversionManager:
        """Return a cached :class:`ConversionManager`, creating one on demand."""
        if self.conversion_manager is None:
            self.conversion_manager = ConversionManager(styles=self.styles)
        return self.conversion_manager

    @property
    def output_rich(self) -> Text:
        """Returns the delta in text with colors/style for the console."""
        console_text = Text()
        style_option = self.options.get('markdown_style') if isinstance(self.options, dict) else None
        insert_style = 'green'
        delete_style = 'strike red'
        if style_option == 'red':
            insert_style = 'red'
        elif style_option in {'red-blue', 'red_blue'}:
            insert_style = 'blue'

        for redline in self.redlines:
            tag, i1, i2, j1, j2 = redline.opcodes
            source_tokens = redline.source_chunk.text
            test_tokens = redline.test_chunk.text

            if tag == 'equal':
                temp_str = ''.join(source_tokens[i1:i2])
                temp_str = temp_str.replace('¶ ', '\n\n')
                console_text.append(temp_str)
            elif tag == 'insert':
                temp_str = ''.join(test_tokens[j1:j2])
                splits = temp_str.split('¶ ')
                for split in splits:
                    console_text.append(split, insert_style)
            elif tag == 'delete':
                console_text.append(''.join(source_tokens[i1:i2]), delete_style)
            elif tag == 'replace':
                console_text.append(''.join(source_tokens[i1:i2]), delete_style)
                temp_str = ''.join(test_tokens[j1:j2])
                splits = temp_str.split('¶ ')
                for split in splits:
                    console_text.append(split, insert_style)

        return console_text

    @property
    def output_json(self) -> dict[str, Any]:
        """Return a structured JSON-serialisable diff payload."""
        changes: list[DiffChange] = []
        insertions = deletions = replacements = equals = 0

        for redline in self.redlines:
            payload = redline.to_dict()
            change_type = payload['type']

            if change_type == 'insert':
                insertions += 1
            elif change_type == 'delete':
                deletions += 1
            elif change_type == 'replace':
                replacements += 1
            else:
                equals += 1

            source_meta = payload['source'].get('metadata') or {}
            test_meta = payload['test'].get('metadata') or {}

            source_segment = DiffSegment(
                start=payload['source'].get('start'),
                end=payload['source'].get('end'),
                text=payload['source'].get('text'),
                xpath=source_meta.get('xpath'),
            )
            test_segment = DiffSegment(
                start=payload['test'].get('start'),
                end=payload['test'].get('end'),
                text=payload['test'].get('text'),
                xpath=test_meta.get('xpath'),
            )

            metadata = payload.get('metadata', {}) or {}
            if source_meta:
                metadata = {**metadata, 'source': source_meta}
            if test_meta:
                metadata = {**metadata, 'test': test_meta}

            changes.append(
                DiffChange(
                    type=change_type,  # type: ignore[arg-type]
                    source=source_segment,
                    test=test_segment,
                    metadata=metadata,
                )
            )

        total_changes = len(changes)
        summary = DiffSummary(
            total_changes=total_changes,
            insertions=insertions,
            deletions=deletions,
            replacements=replacements,
            equals=equals,
        )

        library_version = self._resolve_library_version()
        style = self.options.get('markdown_style') if isinstance(self.options, dict) else None
        processor_name = type(self.processor).__name__
        palette = self.styles.get_diff_palette(style)

        metadata = DiffMetadata(
            library_version=library_version,
            style=style,
            processor=processor_name,
            palette=palette,
            structural_diff=self._structural_diff,
        )

        result = DiffResult(metadata=metadata, summary=summary, changes=changes)
        return result.model_dump(mode='json')

    def to_json_file(self, path: str | Path, *, indent: int = 2) -> Path:
        """Persist :pyattr:`output_json` to disk."""
        payload = self.output_json
        output_path = Path(path)
        output_path.write_text(json.dumps(payload, indent=indent), encoding='utf-8')
        return output_path

    def compare(self, test: str | None = None, output: str = 'markdown', **options):
        """Compare `test` with `source`, and produce a delta in a format specified by `output`.

        :param test: Optional test string to compare. If None, uses the test string provided during initialisation.
        :param output: The format which the delta should be produced. Currently, "markdown", "rich", and "json" are supported. Defaults to "markdown".
        :return: The delta in the format specified by `output`.
        """
        if options:
            self.options = options

        if test:
            if self._test and test == self._test:
                # If we've already processed this test string, no need to reprocess
                pass
            else:
                self.test = test
        elif self._test is None:
            msg = 'No test string was provided when the function was called, or during initialisation.'
            raise ValueError(msg)

        if output == 'markdown':
            return self.output_markdown
        if output == 'rich':
            return self.output_rich
        if output == 'json':
            return self.output_json
        return self.output_markdown