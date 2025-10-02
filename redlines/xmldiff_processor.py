from __future__ import annotations

from typing import Any, Iterable, Optional

from bs4 import BeautifulSoup
from lxml import etree, html
from xmldiff import actions, diff

from .processor import RedlinesProcessor, WholeDocumentProcessor


class XmlDiffProcessor(RedlinesProcessor):
    """HTML/XML-aware processor that enriches token-based diffs with xmldiff output."""

    def __init__(
        self,
        *,
        base_processor: Optional[WholeDocumentProcessor] = None,
        diff_options: Optional[dict[str, Any]] = None,
    ) -> None:
        self._base_processor = base_processor or WholeDocumentProcessor()
        self._structural_diff: list[dict[str, Any]] = []
        self._diff_options = diff_options or {
            'ratio_mode': 'fast',
            'fast_match': True,
            'ignored_attrs': ['class', 'style', 'data-*'],
        }
        self._last_source_html: str = ''
        self._last_test_html: str = ''
        self._raw_actions: list[Any] = []

    @property
    def structural_diff(self) -> list[dict[str, Any]]:
        """Return the most recent structural diff produced by xmldiff."""
        return self._structural_diff

    def process(self, source: Any, test: Any) -> list:
        source_text = source.text if hasattr(source, 'text') else str(source)
        test_text = test.text if hasattr(test, 'text') else str(test)

        self._structural_diff = self._build_structural_diff(source_text, test_text)
        return self._base_processor.process(source_text, test_text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_structural_diff(self, source_html: str, test_html: str) -> list[dict[str, Any]]:
        try:
            sanitized_source = self._sanitize_markup(source_html)
            sanitized_test = self._sanitize_markup(test_html)
            self._last_source_html = sanitized_source
            self._last_test_html = sanitized_test
            left = self._parse_sanitized_html(sanitized_source)
            right = self._parse_sanitized_html(sanitized_test)
        except ValueError:
            return []

        differ = diff.Differ(**self._diff_options)
        actions = list(differ.diff(left, right))
        self._raw_actions = actions
        return [self._action_to_dict(action) for action in actions]

    def _parse_sanitized_html(self, markup: str) -> etree._Element:
        if not markup.strip():
            raise ValueError('Empty markup provided to XmlDiffProcessor')

        parser = html.HTMLParser(remove_blank_text=True, remove_comments=True, encoding='utf-8')
        return html.fromstring(markup.encode('utf-8'), parser=parser)

    @staticmethod
    def _sanitize_markup(markup: str) -> str:
        soup = BeautifulSoup(markup, 'html.parser')
        for tag in soup(['script', 'style']):
            tag.decompose()
        return str(soup)

    @staticmethod
    def _action_to_dict(action: Any) -> dict[str, Any]:  # type: ignore[type-arg]
        payload = {'action': type(action).__name__}
        for key, value in XmlDiffProcessor._iter_action_items(action):
            payload[key] = value
        return payload

    @staticmethod
    def _iter_action_items(action: Any) -> Iterable[tuple[str, Any]]:  # type: ignore[type-arg]
        if hasattr(action, '_asdict'):
            for key, value in action._asdict().items():
                payload_value = value
                if isinstance(value, etree._Element):
                    payload_value = XmlDiffProcessor._element_summary(value)
                yield key, payload_value
        else:  # pragma: no cover - defensive: future proofing
            for key in getattr(action, '_fields', []):
                value = getattr(action, key)
                if isinstance(value, etree._Element):
                    value = XmlDiffProcessor._element_summary(value)
                yield key, value

    @staticmethod
    def _element_summary(element: etree._Element) -> dict[str, Any]:
        tree = element.getroottree()
        xpath = tree.getpath(element)
        text_content = ''.join(element.itertext()).strip()
        return {'xpath': xpath, 'text': text_content}

    def get_debug_snapshot(self) -> dict[str, Any]:
        """Return the latest sanitized HTML and raw actions for debugging."""
        return {
            'source_html': self._last_source_html,
            'test_html': self._last_test_html,
            'raw_actions': [str(action) for action in self._raw_actions],
        }


__all__ = ['XmlDiffProcessor']
