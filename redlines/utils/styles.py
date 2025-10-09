from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open('r', encoding='utf-8') as handle:
        return json.load(handle)


@dataclass(slots=True)
class Styles:
    """Configurator for document layout across processors.

    The class exposes a rich configuration surface covering fonts, headers, footers,
    justification, and heading presets. Defaults are intentionally brand-neutral so
    consumers can layer their own identity on top.
    """

    config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        base = copy.deepcopy(self._default_config())
        self._deep_update(base, self.config)
        self.config = base

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_file(cls, path: str | Path) -> Styles:
        """Build a Styles profile from a JSON file."""
        file_path = Path(path)
        data = _load_json(file_path)
        return cls(config=data)

    @classmethod
    def merge_profiles(cls, profiles: Iterable[Styles]) -> Styles:
        """Merge several style profiles, later profiles overwrite earlier ones."""
        config: Dict[str, Any] = {}
        for profile in profiles:
            cls._deep_update(config, profile.config)
        return cls(config=config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update(self, overrides: Dict[str, Any]) -> None:
        """Update configuration in-place."""
        self._deep_update(self.config, overrides)

    def get_diff_palette(self, style: Optional[str]) -> Dict[str, str]:
        """Return colour palette for diff highlights."""
        palettes: Dict[str, Dict[str, str]] = self.config.get('diff_styles', {})
        if style and style in palettes:
            return palettes[style]
        return palettes.get('red_green', {'insert': '#00875a', 'delete': '#b00020'})

    # DOCX helpers ------------------------------------------------------
    def apply_paragraph_defaults(self, paragraph) -> None:
        """Apply base font + justification to a python-docx paragraph."""
        font_cfg = self.config['font']
        para_cfg = self.config['paragraph']
        paragraph.paragraph_format.line_spacing = para_cfg.get('line_spacing', 1.15)
        space_after = para_cfg.get('space_after_pts', 6)
        paragraph.paragraph_format.space_after = Pt(space_after)
        self._apply_justification(paragraph, self.config.get('text_justification', 'left'))

        for run in paragraph.runs:
            self._apply_run_font(run.font, font_cfg)

    def apply_heading(self, paragraph, level: int) -> None:
        """Apply heading style metadata to a paragraph."""
        key = f'h{level}'
        heading_cfg = self.config['headings'].get(key)
        if not heading_cfg:
            msg = f'Heading level {level} is not configured'
            raise ValueError(msg)

        run = paragraph.runs[0] if paragraph.runs else paragraph.add_run()
        self._apply_run_font(run.font, heading_cfg['font'])
        paragraph.alignment = heading_cfg.get('alignment', WD_ALIGN_PARAGRAPH.LEFT)
        paragraph.paragraph_format.space_before = Pt(heading_cfg.get('space_before_pts', 12))
        paragraph.paragraph_format.space_after = Pt(heading_cfg.get('space_after_pts', 6))

    def configure_document(self, document) -> None:
        """Apply global styles to a python-docx Document."""
        font_cfg = self.config['font']

        normal_style = document.styles['Normal']  # type: ignore[index]
        self._apply_run_font(normal_style.font, font_cfg, is_style=True)  # type: ignore[attr-defined]

        for level in range(1, 7):
            name = f'Heading {level}'
            if name in document.styles:
                heading_style = document.styles[name]  # type: ignore[index]
                self._apply_run_font(heading_style.font, self.config['headings'][f'h{level}']['font'], is_style=True)  # type: ignore[attr-defined]

        for section in document.sections:
            self._setup_header_footer(section.header, self.config['header'])
            self._setup_header_footer(section.footer, self.config['footer'])

    # HTML helpers ------------------------------------------------------
    def build_html_document(self, body: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Return a fully-formed HTML document embedding configured styles."""
        metadata = metadata or {}
        title = metadata.get('title', 'Document')
        font_cfg = self.config['font']
        paragraph_cfg = self.config['paragraph']
        justification = self.config.get('text_justification', 'left')
        justification_css = {
            'left': 'left',
            'right': 'right',
            'center': 'center',
            'justify': 'justify',
        }[justification]

        heading_css = []
        for level in range(1, 7):
            key = f'h{level}'
            heading_cfg = self.config['headings'][key]
            heading_css.append(
                f".content h{level}{{font-family:'{heading_cfg['font']['name']}';font-size:{heading_cfg['font']['size']}pt;"
                f"font-weight:{'700' if heading_cfg['font']['bold'] else '400'};"
                f"font-style:{'italic' if heading_cfg['font']['italic'] else 'normal'};"
                f"margin-top:{heading_cfg.get('space_before_pts', 12)}pt;margin-bottom:{heading_cfg.get('space_after_pts', 6)}pt;"
                f"text-align:{self._alignment_to_css(heading_cfg.get('alignment', WD_ALIGN_PARAGRAPH.LEFT))};}}"
            )

        header_html = self.config['header'].get('content', '') if self.config['header'].get('enabled') else ''
        footer_html = self.config['footer'].get('content', '') if self.config['footer'].get('enabled') else ''

        parts = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            f'<meta charset="utf-8"><title>{title}</title>',
            '<style>',
            f"body{{margin:0;padding:0;font-family:'{font_cfg['name']}';font-size:{font_cfg['size']}pt;color:#000;}}",
            '.document-container{margin:0 auto;max-width:8.27in;padding:1in;box-sizing:border-box;}',
            f".content p{{line-height:{paragraph_cfg.get('line_spacing', 1.15)};margin-bottom:{paragraph_cfg.get('space_after_pts', 6)}pt;text-align:{justification_css};}}",
            '.content table{border-collapse:collapse;width:100%;margin-bottom:12pt;}',
            '.content th,.content td{border:1px solid #333;padding:6pt;text-align:left;}',
            '.content code{font-family:"Courier New",monospace;font-size:10pt;background:#f5f5f5;padding:1pt 3pt;}',
            '.content pre{background:#f5f5f5;padding:12pt;overflow-x:auto;}',
            '.header,.footer{text-align:center;font-size:9pt;color:#555;}',
            '.header{margin-bottom:12pt;}',
            '.footer{margin-top:24pt;border-top:1px solid #ccc;padding-top:12pt;}',
            ''.join(heading_css),
            '</style>',
            '</head>',
            '<body>',
            '<div class="document-container">',
        ]

        if header_html:
            parts.append(f'<div class="header">{header_html}</div>')

        parts.extend(
            [
                '<div class="content">',
                f'{body}',
                '</div>',
            ]
        )

        if footer_html:
            parts.append(f'<div class="footer">{footer_html}</div>')

        parts.extend(['</div>', '</body>', '</html>'])

        return ''.join(parts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _default_config() -> Dict[str, Any]:
        return {
            'font': {
                'name': 'Times New Roman',
                'size': 12,
                'bold': False,
                'italic': False,
                'underline': False,
                'color': {'r': 0, 'g': 0, 'b': 0},
            },
            'paragraph': {
                'line_spacing': 1.2,
                'space_after_pts': 6,
            },
            'diff_styles': {
                'red_green': {'insert': '#00875a', 'delete': '#b00020'},
                'red_blue': {'insert': '#1d4ed8', 'delete': '#b00020'},
                'red': {'insert': '#b00020', 'delete': '#b00020'},
            },
            'header': {
                'enabled': False,
                'first_page_only': False,
                'content': '',
                'font': {'name': 'Times New Roman', 'size': 10, 'bold': False, 'italic': False},
            },
            'footer': {
                'enabled': False,
                'first_page_only': False,
                'content': '',
                'font': {'name': 'Times New Roman', 'size': 10, 'bold': False, 'italic': False},
            },
            'text_justification': 'left',
            'headings': {
                'h1': {
                    'font': {'name': 'Times New Roman', 'size': 18, 'bold': True, 'italic': False},
                    'alignment': WD_ALIGN_PARAGRAPH.CENTER,
                    'space_before_pts': 24,
                    'space_after_pts': 12,
                },
                'h2': {
                    'font': {'name': 'Times New Roman', 'size': 16, 'bold': True, 'italic': False},
                    'alignment': WD_ALIGN_PARAGRAPH.LEFT,
                    'space_before_pts': 18,
                    'space_after_pts': 12,
                },
                'h3': {
                    'font': {'name': 'Times New Roman', 'size': 14, 'bold': True, 'italic': False},
                    'alignment': WD_ALIGN_PARAGRAPH.LEFT,
                    'space_before_pts': 12,
                    'space_after_pts': 8,
                },
                'h4': {
                    'font': {'name': 'Times New Roman', 'size': 12, 'bold': True, 'italic': False},
                    'alignment': WD_ALIGN_PARAGRAPH.LEFT,
                    'space_before_pts': 12,
                    'space_after_pts': 6,
                },
                'h5': {
                    'font': {'name': 'Times New Roman', 'size': 11, 'bold': False, 'italic': True},
                    'alignment': WD_ALIGN_PARAGRAPH.LEFT,
                    'space_before_pts': 12,
                    'space_after_pts': 6,
                },
                'h6': {
                    'font': {'name': 'Times New Roman', 'size': 10, 'bold': False, 'italic': True},
                    'alignment': WD_ALIGN_PARAGRAPH.LEFT,
                    'space_before_pts': 12,
                    'space_after_pts': 6,
                },
            },
        }

    @staticmethod
    def _deep_update(target: Dict[str, Any], updates: Dict[str, Any]) -> None:
        for key, value in updates.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                Styles._deep_update(target[key], value)
            else:
                target[key] = value

    @staticmethod
    def _apply_run_font(font_obj, font_cfg: Dict[str, Any], *, is_style: bool = False) -> None:
        font_obj.name = font_cfg.get('name', font_obj.name)
        size = font_cfg.get('size')
        if size:
            font_obj.size = Pt(size)
        if 'bold' in font_cfg:
            font_obj.bold = font_cfg['bold']
        if 'italic' in font_cfg:
            font_obj.italic = font_cfg['italic']
        if 'underline' in font_cfg:
            font_obj.underline = font_cfg['underline']
        color = font_cfg.get('color')
        if color:
            font_obj.color.rgb = RGBColor(color.get('r', 0), color.get('g', 0), color.get('b', 0))
        if not is_style:
            element = getattr(font_obj, '_element', None)
            if element is not None and element.rPr is not None:
                element.rPr.rFonts.set(qn('w:eastAsia'), font_cfg.get('name', 'Times New Roman'))

    @staticmethod
    def _apply_justification(paragraph, justification: str) -> None:
        mapping = {
            'left': WD_ALIGN_PARAGRAPH.LEFT,
            'right': WD_ALIGN_PARAGRAPH.RIGHT,
            'center': WD_ALIGN_PARAGRAPH.CENTER,
            'justify': WD_ALIGN_PARAGRAPH.JUSTIFY,
        }
        paragraph.alignment = mapping.get(justification, WD_ALIGN_PARAGRAPH.LEFT)

    @staticmethod
    def _alignment_to_css(alignment) -> str:
        mapping = {
            WD_ALIGN_PARAGRAPH.LEFT: 'left',
            WD_ALIGN_PARAGRAPH.RIGHT: 'right',
            WD_ALIGN_PARAGRAPH.CENTER: 'center',
            WD_ALIGN_PARAGRAPH.JUSTIFY: 'justify',
        }
        return mapping.get(alignment, 'left')

    def _setup_header_footer(self, part, cfg: Dict[str, Any]) -> None:
        if not cfg.get('enabled'):
            # clear existing text without leaving empty paragraphs that could cause layout artifacts
            for paragraph in part.paragraphs:
                paragraph.text = ''
            return

        content = cfg.get('content', '')
        if not content:
            return

        paragraph = part.paragraphs[0] if part.paragraphs else part.add_paragraph()
        paragraph.text = content
        if paragraph.runs:
            self._apply_run_font(paragraph.runs[0].font, cfg['font'])
        self._apply_justification(paragraph, cfg.get('alignment', 'center'))
