from bs4 import BeautifulSoup, NavigableString
from typing import List, Tuple, Dict, Optional

class StyleParser:
    """
    Parses HTML to extract text segments and their corresponding styles.
    """

    def parse(self, html_string: str) -> List[Tuple[str, Optional[Dict[str, str]]]]:
        """
        Parses an HTML string to extract text segments and their associated styles.

        Args:
            html_string: The HTML content to parse.

        Returns:
            A list of tuples, where each tuple contains:
            - A string of text.
            - A dictionary of styles for that text, or None.
        """
        soup = BeautifulSoup(html_string, 'html.parser')
        segments = []

        for element in soup.find_all(string=True):
            if isinstance(element, NavigableString):
                parent = element.parent
                style_dict = self.get_style(parent)

                text = str(element)
                # Whitespace is significant in this model, so we don't strip it.
                if text:
                    segments.append((text, style_dict))

        return segments

    def get_style(self, tag) -> Optional[Dict[str, str]]:
        """
        Extracts the CSS styles from a BeautifulSoup tag by traversing its parents.
        """
        if not tag:
            return None

        style_dict = {}
        # Traverse from the current tag up to its parents
        for parent in [tag] + list(tag.parents):
            if not hasattr(parent, 'name'):
                continue

            # Tag-based styling
            if parent.name in ['b', 'strong']:
                if 'font-weight' not in style_dict:
                    style_dict['font-weight'] = 'bold'
            if parent.name in ['i', 'em']:
                if 'font-style' not in style_dict:
                    style_dict['font-style'] = 'italic'
            if parent.name == 'u':
                if 'text-decoration' not in style_dict:
                    style_dict['text-decoration'] = 'underline'

            if not hasattr(parent, 'attrs'):
                continue

            # Direct style attribute
            inline_style = parent.attrs.get('style', '')
            if inline_style:
                # This is a simplified style parser. A more robust solution would
                # parse the style string properly.
                for style_rule in inline_style.split(';'):
                    if ':' in style_rule:
                        key, value = style_rule.split(':', 1)
                        key = key.strip()
                        if key not in style_dict:
                            style_dict[key] = value.strip()

        return style_dict if style_dict else None