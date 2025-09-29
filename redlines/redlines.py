from __future__ import annotations

from typing import Any, Optional, Tuple

from rich.text import Text

from redlines.document import Document
from redlines.processor import Redline, WholeDocumentProcessor
from redlines.utils.conversion_manager import ConversionManager
from redlines.utils.styles import Styles


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
        content, fmt_hint, metadata = self._unpack_input(value, self._pending_source_format, self._pending_source_metadata)
        self._source_format = fmt_hint
        self._source_metadata = metadata
        self._source = self._coerce_to_text(content, fmt_hint)
        self._pending_source_format = None
        self._pending_source_metadata = None

        if self._test is not None:
            self._redlines = self.processor.process(self._source, self._test)

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

        if self._source is not None and self._test is not None:
            self._redlines = self.processor.process(self._source, self._test)

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
        self.processor = WholeDocumentProcessor()

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

    @property
    def output_markdown(self) -> str:
        """Returns the delta in Markdown format.

        ## Styling Markdown
        To output markdown in a particular manner, you must pass a `markdown_style` option when the `Redlines` object
        is created or when `Redlines.compare` is called.

        ```python
        from redlines import Redlines

        test = Redlines(
            'The quick brown fox jumps over the lazy dog.',
            'The quick brown fox walks past the lazy dog.',
            markdown_style='red',  # This option specifies the style as red
        )

        test.compare(markdown_style='none')  # This option specifies the style as none
        ```

        ### Available styles

        | Style | Preview |
        |-------| -------|
        |red-green (**default**) | "The quick brown fox <span style='color:red;font-weight:700;text-decoration:line-through;'>jumps over </span><span style='color:green;font-weight:700;'>walks past </span>the lazy dog."|
        |none | 'The quick brown fox <del>jumps over </del><ins>walks past </ins>the lazy dog.'|
        |red | "The quick brown fox <span style='color:red;font-weight:700;text-decoration:line-through;'>jumps over </span><span style='color:red;font-weight:700;'>walks past </span>the lazy dog."|
        |ghfm (GitHub Flavored Markdown)| 'The quick brown fox ~~jumps over ~~**walks past **the lazy dog.' |
        |bbcode (BBCode) | 'The quick brown fox [s][color=red]jumps over [/color][/s][b][color=green]walks past [/color][/b]the lazy dog.' |
        |streamlit | 'The quick brown fox ~~:red[jumps over ]~~ **:green[walks past ]** the lazy dog.' |

        ### Custom styling

        You can also use css classes to provide custom styling by setting `markdown_style` as "custom_css".
        Insertions and deletions are now styled using the "redline-inserted" and "redline-deleted" CSS classes.
        You can also set your own CSS classes by specifying the name of the CSS class in the options `ins_class`
        and `del_class` respectively in the constructor or compare function.

        ## Markdown output in specific environments

        Users have reported that the output doesn't display correctly in their environments.
        This is because styling may not appear in markdown environments which disallow HTML.
        There is no consistent support for strikethroughs and colors in the markdown standard,
        and styling is largely accomplished through raw HTML. If you are using GitHub or Streamlit, you may not get
        the formatting you expect or see any change at all.

        If you are facing this kind of difficulty, here are some recommendations. If your experience doesn't match
        the hints or description below, or you continue to face problems, please raise an issue.

        ### Jupyter Notebooks
        This library was first written for the Jupyter notebook environment, so all the available styles, including
        the default (`red-green`), `red` and `none` work.

        ### Streamlit

        Try this:

        * If streamlit version is >= 1.16.0, consider the markdown style "streamlit"
        * If streamlit version is < 1.16.0, consider the markdown style `ghfm`
        * Enable parsing of HTML. In Streamlit, you need to set the `unsafe_allow_html` argument in `st.write` or
        `st.markdown` to `True`.

        ### Colab

        Try this:
        * Use the markdown style `none` or `ghfm`
        * `Redlines.output_rich` has been reported to work in Colab

        """
        result = []

        # default_style = "red_green"

        md_styles = {
            'ins': ("<span style='color:green;font-weight:700;'>", '</span>'),
            'del': ("<span style='color:red;font-weight:700;text-decoration:line-through;'>", '</span>'),
        }

        if 'markdown_style' in self.options:
            style = self.options['markdown_style']

            if style == 'none' or style is None:
                md_styles = {'ins': ('<ins>', '</ins>'), 'del': ('<del>', '</del>')}
            elif style == 'red':
                md_styles = {
                    'ins': ("<span style='color:red;font-weight:700;'>", '</span>'),
                    'del': ("<span style='color:red;font-weight:700;text-decoration:line-through;'>", '</span>'),
                }
            elif style == 'custom_css':
                ins_class = self.options.get('ins_class', 'redline-inserted')
                del_class = self.options.get('del_class', 'redline-deleted')

                elem_attributes = {'ins': f"class='{ins_class}'", 'del': f"class='{del_class}'"}

                md_styles = {
                    'ins': (f'<span {elem_attributes["ins"]}>', '</span>'),
                    'del': (f'<span {elem_attributes["del"]}>', '</span>'),
                }
            elif style == 'ghfm':
                md_styles = {'ins': ('**', '**'), 'del': ('~~', '~~')}
            elif style == 'bbcode':
                md_styles = {'ins': ('[b][color=green]', '[/color][/b]'), 'del': ('[s][color=red]', '[/color][/s]')}
            elif style == 'streamlit':
                md_styles = {'ins': ('**:green[', ']** '), 'del': ('~~:red[', ']~~ ')}

        for redline in self.redlines:
            tag, i1, i2, j1, j2 = redline.opcodes
            source_tokens = redline.source_chunk.text
            test_tokens = redline.test_chunk.text

            if tag == 'equal':
                temp_str = ''.join(source_tokens[i1:i2])
                temp_str = temp_str.replace('¶ ', '\n\n')
                # here we use '¶ ' instead of ' ¶ ', because the leading space will be included in the previous token,
                # according to tokenizer = re.compile(r"((?:[^()\s]+|[().?!-])\s*)")
                result.append(temp_str)
            elif tag == 'insert':
                temp_str = ''.join(test_tokens[j1:j2])
                splits = temp_str.split('¶ ')
                for split in splits:
                    result.extend((f'{md_styles["ins"][0]}{split}{md_styles["ins"][1]}', '\n\n'))
                if len(splits) > 0:
                    result.pop()
            elif tag == 'delete':
                result.append(f'{md_styles["del"][0]}{"".join(source_tokens[i1:i2])}{md_styles["del"][1]}')
                # for 'delete', we make no change, because otherwise there will be two times '\n\n' than the original
                # text.
            elif tag == 'replace':
                result.append(f'{md_styles["del"][0]}{"".join(source_tokens[i1:i2])}{md_styles["del"][1]}')
                temp_str = ''.join(test_tokens[j1:j2])
                splits = temp_str.split('¶ ')
                for split in splits:
                    result.extend((f'{md_styles["ins"][0]}{split}{md_styles["ins"][1]}', '\n\n'))
                if len(splits) > 0:
                    result.pop()

        return ''.join(result)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _unpack_input(
        self,
        value: Any,
        default_format: Optional[str],
        default_metadata: Optional[dict[str, Any]],
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
                    console_text.append(split, 'green')
            elif tag == 'delete':
                console_text.append(''.join(source_tokens[i1:i2]), 'strike red')
            elif tag == 'replace':
                console_text.append(''.join(source_tokens[i1:i2]), 'strike red')
                temp_str = ''.join(test_tokens[j1:j2])
                splits = temp_str.split('¶ ')
                for split in splits:
                    console_text.append(split, 'green')

        return console_text

    def compare(self, test: str | None = None, output: str = 'markdown', **options):
        """Compare `test` with `source`, and produce a delta in a format specified by `output`.

        :param test: Optional test string to compare. If None, uses the test string provided during initialisation.
        :param output: The format which the delta should be produced. Currently, "markdown" and "rich" are supported. Defaults to "markdown".
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
        return self.output_markdown
