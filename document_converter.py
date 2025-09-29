from __future__ import annotations

import asyncio
import contextlib
import logging
import warnings
from enum import Enum
from io import BytesIO
from typing import TYPE_CHECKING

import mistune
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from html4docx import HtmlToDocx
from mistune.plugins.abbr import abbr
from mistune.plugins.def_list import def_list
from mistune.plugins.footnotes import footnotes
from mistune.plugins.formatting import insert, mark, strikethrough, subscript, superscript
from mistune.plugins.table import table
from mistune.plugins.task_lists import task_lists
from mistune.plugins.url import url
from weasyprint import HTML
from xhtml2pdf import pisa

if TYPE_CHECKING:
    from docx.document import Document as DocumentType

# Configure logging
logger = logging.getLogger(__name__)
logging.getLogger('weasyprint').setLevel(logging.ERROR)
logging.getLogger('fontTools').setLevel(logging.ERROR)

# Define mistune plugins to use
MISTUNE_PLUGINS = [
    strikethrough,
    footnotes,
    table,
    task_lists,
    insert,
    def_list,
    abbr,
    mark,
    subscript,
    url,
    superscript,
]


# Default table style for DOCX to ensure subtle visible borders
DOCX_DEFAULT_TABLE_STYLE = 'Table Grid'


# src/cicero_mail_pydantic_ptbr/utils/document_converter.py


def _build_markdown_parser(hard_wrap: bool = True):
    """Create a Mistune Markdown parser with desired plugins and hard-wrap behavior."""
    renderer = mistune.HTMLRenderer()
    inline = mistune.InlineParser(hard_wrap=hard_wrap)
    return mistune.Markdown(renderer=renderer, inline=inline, plugins=MISTUNE_PLUGINS)


def _get_document_config():
    """Get document configuration parameters."""
    return 'Times New Roman', 12


class MimeType(Enum):
    """MIME type enumeration for supported file formats."""

    CSS = 'text/css'
    CSV = 'text/csv'
    DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    HTML = 'text/html'
    JS = 'text/javascript'
    JAVA = 'text/x-java-source'
    JSON = 'application/json'
    LATEX = 'application/x-tex'
    MD = 'text/markdown'
    PDF = 'application/pdf'
    PHP = 'application/x-httpd-php'
    PNG = 'image/png'
    PPTX = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    PY = 'text/x-python'
    RST = 'text/prs.fallenstein.rst'
    RUBY = 'text/x-ruby'
    TXT = 'text/plain'
    SH = 'application/x-sh'
    SVG = 'image/svg+xml'
    XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    XML = 'text/xml'
    YAML = 'text/yaml'
    ZIP = 'application/zip'

    @classmethod
    def get_extension(cls, mime_type: str) -> str:
        """Get file extension by mime type."""
        mime_type_map = {
            cls.CSS.value: '.css',
            cls.CSV.value: '.csv',
            cls.DOCX.value: '.docx',
            cls.HTML.value: '.html',
            cls.JS.value: '.js',
            cls.JAVA.value: '.java',
            cls.JSON.value: '.json',
            cls.LATEX.value: '.tex',
            cls.MD.value: '.md',
            cls.PDF.value: '.pdf',
            cls.PHP.value: '.php',
            cls.PNG.value: '.png',
            cls.PPTX.value: '.pptx',
            cls.PY.value: '.py',
            cls.RST.value: '.rst',
            cls.RUBY.value: '.rb',
            cls.TXT.value: '.txt',
            cls.SH.value: '.sh',
            cls.SVG.value: '.svg',
            cls.XLSX.value: '.xlsx',
            cls.XML.value: '.xml',
            cls.YAML.value: '.yaml',
            cls.ZIP.value: '.zip',
        }
        return mime_type_map.get(mime_type, '.bin')


def _generate_legal_html(
    html_content_to_pdf: str, cicero_request_id: str | None = None, include_request_id: bool = True
) -> str:
    """Generate HTML with legal document formatting optimized for PDF generation."""
    cicero_id_html = ''
    if include_request_id and cicero_request_id:
        cicero_id_html = f'<div class="cicero-id-discreet">Request ID: {cicero_request_id}</div>'

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Cicero Document</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;500;900&display=swap" rel="stylesheet">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;500;900&display=swap');

            @page {{
                size: letter;
                margin: 1in 1in 1.5in 1in; /* Extra bottom margin for footer */
                @top-left {{
                    content: "";
                }}
            }}

            @page:left {{
                @bottom-left {{
                    content: "Cicero Assistant";
                    font-family: 'Times New Roman', Times, serif;
                    font-size: 10pt;
                    font-weight: bold;
                }}
                @bottom-right {{
                    content: "www.cicero.im";
                    font-family: 'Times New Roman', Times, serif;
                    font-size: 10pt;
                    font-weight: bold;
                }}
            }}

            @page:right {{
                @bottom-left {{
                    content: "Cicero Assistant";
                    font-family: 'Times New Roman', Times, serif;
                    font-size: 10pt;
                    font-weight: bold;
                }}
                @bottom-right {{
                    content: "www.cicero.im";
                    font-family: 'Times New Roman', Times, serif;
                    font-size: 10pt;
                    font-weight: bold;
                }}
            }}

            @page:first {{
                @top-left {{
                    content: "CICERO";
                    font-family: 'Inter', sans-serif;
                    font-size: 14pt;
                    font-weight: 900;
                }}
                @top-right {{
                    content: "assistant@cicero.im";
                    font-family: 'Times New Roman', Times, serif;
                    font-size: 12pt;
                    font-weight: bold;
                }}
                @bottom-left {{
                    content: none;
                }}
                @bottom-right {{
                    content: none;
                }}
            }}

            body {{
                font-family: 'Times New Roman', Times, serif;
                color: #000000;
                margin: 0;
                padding: 0;
                background: white;
                position: relative;
                min-height: 100vh;
            }}

            .document-container {{
                max-width: 8.5in;
                margin: 0 auto;
                padding: 0;
                position: relative;
                min-height: 100vh;
                padding-bottom: 80px; /* Space for footer */
            }}

            /* Only show on first page for fallback rendering */
            .first-page-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 5px;
                padding-bottom: 5px;
                border-bottom: 1px solid #000000;
                font-family: 'Inter', sans-serif;
            }}

            .first-page-header strong {{
                font-weight: 900;
                font-size: 14pt;
            }}

            .first-page-header a {{
                color: #0000EE;
                text-decoration: none;
                font-size: 14pt;
                font-family: 'Times New Roman', Times, serif;
            }}

            .first-page-header a:hover {{
                text-decoration: underline;
            }}

            /* Hide header on print (since we use @page for proper headers) */
            @media print {{
                .first-page-header {{
                    display: none;
                }}
            }}

            .content {{
                font-family: 'Times New Roman', Times, serif;
                line-height: 1.2;
                color: #000000;
            }}

            /* Heading styles */
            .content h1 {{
                font-size: 14pt;
                font-weight: bold;
                margin-top: 12pt;
                margin-bottom: 6pt;
                color: #000000;
                page-break-after: avoid;
            }}

            .content h2 {{
                font-size: 13pt;
                font-weight: bold;
                margin-top: 12pt;
                margin-bottom: 6pt;
                color: #000000;
                page-break-after: avoid;
            }}

            .content h3 {{
                font-size: 12pt;
                font-weight: bold;
                margin-top: 12pt;
                margin-bottom: 6pt;
                color: #000000;
                page-break-after: avoid;
            }}

            .content h4, .content h5, .content h6 {{
                font-size: 12pt;
                font-weight: bold;
                margin-top: 12pt;
                margin-bottom: 6pt;
                color: #000000;
                font-style: italic;
                page-break-after: avoid;
            }}

            /* Paragraph formatting */
            .content p {{
                font-family: 'Times New Roman', Times, serif;
                color: #000000;
                margin-bottom: 12pt;
                text-align: justify;
            }}

            /* List formatting */
            .content ul, .content ol {{
                font-family: 'Times New Roman', Times, serif;
                color: #000000;
                margin-bottom: 12pt;
            }}

            .content li {{
                font-family: 'Times New Roman', Times, serif;
                color: #000000;
                margin-bottom: 6pt;
                text-align: justify;
            }}

            /* Ensure all text elements have correct formatting */
            .content strong, .content em, .content code {{
                color: #000000;
            }}

            .content strong {{
                font-weight: bold;
            }}

            .content em {{
                font-style: italic;
            }}

            /* Strikethrough support */
            .content del {{
                text-decoration: line-through;
                color: #000000;
            }}

            /* Blockquote formatting */
            .content blockquote {{
                border-left: 3px solid #ccc;
                padding-left: 15px;
                margin-left: 0.5in;
                margin-right: 0.5in;
                margin-bottom: 12pt;
                color: #000000;
                font-family: 'Times New Roman', Times, serif;
                page-break-inside: avoid;
            }}

            /* Table formatting */
            .content table {{
                border-collapse: collapse;
                width: 100%;
                margin-bottom: 12pt;
                page-break-inside: avoid;
            }}

            .content th, .content td {{
                font-family: 'Times New Roman', Times, serif;
                color: #000000;
                border: 1px solid #000000;
                padding: 6pt;
                text-align: left;
            }}

            .content th {{
                font-weight: bold;
            }}

            /* Code formatting */
            .content code {{
                font-family: 'Courier New', Courier, monospace;
                font-size: 10pt;
                background-color: #f5f5f5;
                padding: 1pt 3pt;
                color: #000000;
            }}

            .content pre {{
                font-family: 'Courier New', Courier, monospace;
                font-size: 10pt;
                background-color: #f5f5f5;
                padding: 12pt;
                margin-bottom: 12pt;
                overflow-x: auto;
                page-break-inside: avoid;
            }}

            .content pre code {{
                background-color: transparent;
                padding: 0;
                color: #000000;
            }}

            .cicero-id-discreet {{
                font-size: 8pt;
                color: #999;
                text-align: right;
                margin: 20px 0 0 0;
                padding-top: 10px;
                border-top: 1px solid #ddd;
            }}
            /* Fix task list checkbox display with proper square dimensions */
            .task-list-item-checkbox {{
                display: inline-block;
                width: 1.1em;  /* Slightly wider to compensate for rendering */
                height: 1em;   /* Height matches text */
                min-width: 1.1em;  /* Prevent width compression */
                margin-right: 0.5em;
                margin-top: 0;
                margin-bottom: 0;
                vertical-align: middle;
                cursor: default;
                -webkit-appearance: checkbox;
                -moz-appearance: checkbox;
                appearance: checkbox;
                font-size: 12pt;
                box-sizing: border-box;  /* Include borders in dimensions */
                flex-shrink: 0;  /* Prevent shrinking in flexbox contexts */
            }}

            .task-list-item {{
                list-style-type: none;
                padding-left: 0;
                margin-left: 0;
                font-size: 12pt;
            }}

            .task-list-item p {{
                display: inline;
                margin: 0;
            }}

            /* Ensure checkboxes maintain square shape in print */
            @media print {{
                .task-list-item-checkbox {{
                    width: 1.1em !important;
                    height: 1em !important;
                    min-width: 1.1em !important;
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
            }}

            /* Page numbers for print */
            @media print {{
                body, .content * {{
                    color: #000000 !important;
                }}

                @page {{
                    counter-increment: page;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="document-container">
            <div class="first-page-header">
                <strong>CICERO</strong>
                <a href="mailto:assistant@cicero.im" style="font-weight: bold;">assistant@cicero.im</a>
            <hr style="margin: 1px 0; border: none; border-top: 1px solid #ccc;">
            </div>
            <div class="content">
                {html_content_to_pdf}
                {cicero_id_html}
            </div>
            <!-- Content Division with line separator -->
            <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ccc; font-family: 'Times New Roman', Times, serif; font-size: 12pt; line-height: 1.5;">
                <p style="margin: 10px 0;">Cicero: please draft, modify, research. <i>Will do.</i></p>
                <p style="margin: 10px 0;">***</p>
                <p style="margin: 10px 0;">Cícero: <i>o seu melhor estagiário</i></p>
            </div>
        </div>
    </body>
    </html>
    """


async def markdown_to_pdf(
    markdown_content: str, cicero_request_id: str | None = None, include_request_id: bool = True
) -> bytes:
    """Convert markdown to PDF with fallback mechanism."""
    # Use mistune with hard_wrap to preserve line breaks across formats
    markdown_parser = _build_markdown_parser(hard_wrap=True)
    html_content_to_pdf = markdown_parser(markdown_content)

    # Ensure html_content_to_pdf is a string for _generate_legal_html
    if not isinstance(html_content_to_pdf, str):
        # If mistune returns a non-string (unlikely with standard usage), convert it
        html_content_to_pdf = str(html_content_to_pdf)

    # Generate full HTML document with legal formatting
    html_document = _generate_legal_html(html_content_to_pdf, cicero_request_id, include_request_id)

    # Try WeasyPrint first (better quality)
    try:
        logger.info('Attempting PDF conversion with WeasyPrint...')
        pdf_bytes = await markdown_to_pdf_weasyprint(html_document)
        logger.info('Successfully converted markdown to PDF using WeasyPrint')
        return pdf_bytes
    except Exception as e:
        logger.warning(f'WeasyPrint conversion failed: {str(e)[:100]}. Trying xhtml2pdf...')

        # Fallback to xhtml2pdf
        try:
            pdf_bytes = await markdown_to_pdf_pisa(html_document)
            logger.info('Successfully converted markdown to PDF using xhtml2pdf')
            return pdf_bytes
        except Exception as e2:
            logger.exception(
                f'Both PDF conversion methods failed. WeasyPrint: {str(e)[:100]}, xhtml2pdf: {str(e2)[:100]}'
            )
            msg = f'Failed to convert markdown to PDF: {e2}'
            raise Exception(msg)


async def markdown_to_pdf_pisa(html_document: str) -> bytes:
    """Convert HTML to PDF using xhtml2pdf (pisa)."""
    output_pdf = BytesIO()

    # Simplify HTML for xhtml2pdf (remove unsupported features)
    import re

    html_document = re.sub(r'background:\s*linear-gradient[^;]+;', 'background: #FF4040;', html_document)

    # Define a function to run the PDF creation in a separate thread
    def _create_pdf():
        return pisa.CreatePDF(html_document, dest=output_pdf)

    # Run the blocking PDF creation in a separate thread to avoid blocking the event loop
    pisa_status = await asyncio.to_thread(_create_pdf)

    if pisa_status.err:
        msg = f'xhtml2pdf conversion error: {pisa_status.err}'
        raise Exception(msg)

    # Get the PDF bytes
    output_pdf.seek(0)
    return output_pdf.getvalue()


async def markdown_to_pdf_weasyprint(html_document: str) -> bytes:
    """Convert HTML to PDF using WeasyPrint."""
    await asyncio.sleep(0.01)

    try:
        # Suppress font subsetting logs
        def _generate_pdf():
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                # Generate PDF using WeasyPrint
                return HTML(string=html_document).write_pdf()

        # Run the blocking PDF generation in a separate thread to avoid blocking the event loop
        return await asyncio.to_thread(_generate_pdf)
    except Exception as e:
        msg = f'WeasyPrint conversion error: {e}'
        raise Exception(msg)


async def async_markdown_to_docx_bytes(markdown_text: str) -> bytes:
    """Asynchronously converts markdown text to DOCX bytes with legal formatting."""
    try:
        # Get document configuration
        font_family, font_size = _get_document_config()

        # Use mistune with hard_wrap to preserve line breaks
        markdown_parser = _build_markdown_parser(hard_wrap=True)
        html_content = markdown_parser(markdown_text)

        # Try html4docx first
        try:
            parser = HtmlToDocx()
            # Ensure tables use a subtle visible border style by default
            with contextlib.suppress(Exception):
                parser.table_style = DOCX_DEFAULT_TABLE_STYLE
            # Parse the HTML content while preserving formatting
            docx_document = parser.parse_html_string(html_content)

            # Apply legal formatting to the document
            docx_document = _apply_legal_formatting(docx_document, font_family, font_size)

            # Add the centered text division at the end
            _add_docx_centered_division(docx_document)

            # Save to memory
            docx_bytes = BytesIO()
            docx_document.save(docx_bytes)
            docx_bytes.seek(0)

            logger.info('Successfully converted markdown to DOCX using html4docx with mistune')
            return docx_bytes.getvalue()

        except Exception as e:
            logger.warning(f'html4docx conversion failed: {str(e)[:100]}. Using python-docx directly...')
            # Fallback: Create DOCX manually with python-docx
            return await _markdown_to_docx_manual(markdown_text, font_family, font_size)

    except Exception as e:
        logger.exception('Failed to convert markdown to DOCX: %s', e)
        raise


def _apply_legal_formatting(
    doc: DocumentType, font_family: str = 'Times New Roman', font_size: int = 12
) -> DocumentType:
    """Apply legal document formatting to a DOCX document."""
    # Add header and footer to the document
    _add_docx_header_footer(doc)

    # Set styles for the document
    styles = doc.styles

    # Normal style
    if 'Normal' in styles:
        normal_style = styles['Normal']
        normal_style.font.name = font_family
        normal_style.font.size = Pt(font_size)
        normal_style.font.color.rgb = RGBColor(0, 0, 0)

    # Heading styles
    for i in range(1, 7):  # Support all 6 heading levels
        heading_name = f'Heading {i}'
        if heading_name in styles:
            heading_style = styles[heading_name]
            heading_style.font.name = font_family
            heading_style.font.color.rgb = RGBColor(0, 0, 0)
            heading_style.font.bold = True

            if i == 1:
                heading_style.font.size = Pt(14)
            elif i == 2:
                heading_style.font.size = Pt(13)
            else:
                heading_style.font.size = Pt(12)

    # Ensure tables have a subtle visible border style if none was applied
    for tbl in doc.tables:
        try:
            current_style_name = getattr(getattr(tbl, 'style', None), 'name', None)
            if tbl.style is None or current_style_name in {None, 'Normal Table'}:
                tbl.style = DOCX_DEFAULT_TABLE_STYLE
        except Exception:
            # If style lookup fails or style doesn't exist in template, skip silently
            pass

    # Apply specific formatting to existing paragraphs only where needed
    for paragraph in doc.paragraphs:
        # Set paragraph formatting
        paragraph.paragraph_format.line_spacing = 1.2
        paragraph.paragraph_format.space_after = Pt(6)

        # Justify text (except headings)
        if not paragraph.style.name.startswith('Heading'):
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        for run in paragraph.runs:
            run.font.name = font_family

    return doc


async def _markdown_to_docx_manual(
    markdown_text: str, font_family: str = 'Times New Roman', font_size: int = 12
) -> bytes:
    """Manually convert markdown to DOCX with proper legal formatting."""
    import re

    # Create a new Document
    doc = Document()

    # Add header and footer to the document
    _add_docx_header_footer(doc)

    # Set up legal document formatting
    # The style is actually a ParagraphStyle at runtime, but type checker sees BaseStyle
    # Using type: ignore to suppress the false positive since we know "Normal" is a paragraph style
    normal_style = doc.styles['Normal']  # type: ignore[assignment]
    normal_style.font.name = font_family
    normal_style.font.size = Pt(font_size)
    normal_style.font.color.rgb = RGBColor(0, 0, 0)

    # Parse markdown and add to document
    lines = markdown_text.split('\n')
    current_paragraph = None
    in_code_block = False
    code_block_content = []

    for line in lines:
        # Handle code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block
                code_text = '\n'.join(code_block_content)
                p = doc.add_paragraph()
                p.style = 'Normal'
                run = p.add_run(code_text)
                run.font.name = 'Courier New'
                run.font.size = Pt(10)
                code_block_content = []
                in_code_block = False
            else:
                # Start code block
                in_code_block = True
            current_paragraph = None
            continue

        if in_code_block:
            code_block_content.append(line)
            continue

        line = line.rstrip()

        if not line:
            # Empty line, start new paragraph
            current_paragraph = None
            continue

        # Handle headings
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            heading_text = line.lstrip('#').strip()
            p = doc.add_heading(heading_text, level=min(level, 6))

            # Apply legal formatting to heading
            for run in p.runs:
                run.font.name = font_family
                run.font.color.rgb = RGBColor(0, 0, 0)
                if level == 1:
                    run.font.size = Pt(14)
                elif level == 2:
                    run.font.size = Pt(13)
                else:
                    run.font.size = Pt(12)

            current_paragraph = None

        # Handle list items
        elif line.lstrip().startswith(('- ', '* ', '+ ')):
            indent_level = (len(line) - len(line.lstrip())) // 2
            item_text = re.sub(r'^[\s\-\*\+]+', '', line).strip()
            p = doc.add_paragraph(item_text, style='List Bullet')
            if indent_level > 0:
                p.paragraph_format.left_indent = Pt(36 * indent_level)
            _format_paragraph(p)
            current_paragraph = None

        elif re.match(r'^\s*\d+\.\s', line):
            indent_level = (len(line) - len(line.lstrip())) // 2
            item_text = re.sub(r'^\s*\d+\.\s*', '', line).strip()
            p = doc.add_paragraph(item_text, style='List Number')
            if indent_level > 0:
                p.paragraph_format.left_indent = Pt(36 * indent_level)
            _format_paragraph(p)
            current_paragraph = None

        # Handle blockquotes
        elif line.strip().startswith('>'):
            quote_text = line.strip().lstrip('>').strip()
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(36)
            p.paragraph_format.right_indent = Pt(36)
            _add_formatted_text(p, quote_text)
            _format_paragraph(p)
            current_paragraph = None

        # Regular paragraph
        else:
            if current_paragraph is None:
                current_paragraph = doc.add_paragraph()
                _format_paragraph(current_paragraph)
            else:
                current_paragraph.add_run(' ')

            # Process inline formatting
            _add_formatted_text(current_paragraph, line)

    # Add the centered text division at the end
    _add_docx_centered_division(doc)

    # Save to BytesIO
    docx_bytes = BytesIO()
    doc.save(docx_bytes)
    docx_bytes.seek(0)

    logger.info('Successfully converted markdown to DOCX using manual method')
    return docx_bytes.getvalue()


def _format_paragraph(paragraph) -> None:
    """Apply legal formatting to a paragraph."""
    paragraph.paragraph_format.line_spacing = 1.2
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for run in paragraph.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0, 0, 0)


def _add_formatted_text(paragraph, text) -> None:
    """Add text with inline formatting to a paragraph."""
    import re

    # Process inline formatting with proper regex
    last_end = 0

    # Combined pattern for all inline formatting
    pattern = r'(\*\*(.+?)\*\*)|(\*(.+?)\*)|(__(.+?)__)|(\_(.+?)\_)|(`(.+?)`)'

    for match in re.finditer(pattern, text):
        # Add text before the match
        if match.start() > last_end:
            plain_text = text[last_end : match.start()]
            run = paragraph.add_run(plain_text)
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(0, 0, 0)

        # Add formatted text
        if match.group(1):  # **bold**
            run = paragraph.add_run(match.group(2))
            run.bold = True
        elif match.group(3):  # *italic*
            run = paragraph.add_run(match.group(4))
            run.italic = True
        elif match.group(5):  # __bold__
            run = paragraph.add_run(match.group(6))
            run.bold = True
        elif match.group(7):  # _italic_
            run = paragraph.add_run(match.group(8))
            run.italic = True
        elif match.group(9):  # `code`
            run = paragraph.add_run(match.group(10))
            run.font.name = 'Courier New'
            run.font.size = Pt(10)

        run.font.color.rgb = RGBColor(0, 0, 0)
        last_end = match.end()

    # Add remaining text
    if last_end < len(text):
        plain_text = text[last_end:]
        run = paragraph.add_run(plain_text)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0, 0, 0)


def _add_docx_header_footer(doc: DocumentType) -> None:
    """Add header and footer to DOCX document with logo, email, and footer text."""
    # Access the sections (there's usually one section in a new document)
    sections = doc.sections

    for section in sections:
        # Enable different first page header/footer
        section.different_first_page_header_footer = True

        # Calculate full page width for proper table sizing
        page_width = section.page_width
        left_margin = section.left_margin
        right_margin = section.right_margin
        table_width = page_width - left_margin - right_margin

        # === FIRST PAGE HEADER (with logo and email) ===
        first_header = section.first_page_header
        first_header_para = first_header.paragraphs[0] if first_header.paragraphs else first_header.add_paragraph()
        first_header_para.clear()

        # Create table for first page header
        if not first_header.tables:
            first_header_table = first_header.add_table(rows=1, cols=2, width=table_width)
            first_header_table.autofit = False
            first_header_table.columns[0].width = int(table_width * 0.6)  # 60% for logo
            first_header_table.columns[1].width = int(table_width * 0.4)  # 40% for email
        else:
            first_header_table = first_header.tables[0]

        # Remove table borders
        for row in first_header_table.rows:
            for cell in row.cells:
                tc = cell._element
                tcPr = tc.get_or_add_tcPr()
                tcBorders = OxmlElement('w:tcBorders')
                for border_name in ['top', 'left', 'bottom', 'right']:
                    border = OxmlElement(f'w:{border_name}')
                    border.set(qn('w:val'), 'nil')
                    tcBorders.append(border)
                tcPr.append(tcBorders)

        # Left cell: CICERO logo (only on first page)
        left_cell = first_header_table.rows[0].cells[0]
        left_para = left_cell.paragraphs[0] if left_cell.paragraphs else left_cell.add_paragraph()
        left_para.clear()
        left_para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

        logo_run = left_para.add_run('CICERO')
        logo_run.font.name = 'Georgia'  # Using Georgia as a serif fallback for Inter
        logo_run.font.size = Pt(14)
        logo_run.font.bold = True
        logo_run.font.color.rgb = RGBColor(0, 0, 0)

        # Right cell: Email (only on first page)
        right_cell = first_header_table.rows[0].cells[1]
        right_para = right_cell.paragraphs[0] if right_cell.paragraphs else right_cell.add_paragraph()
        right_para.clear()
        right_para.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

        email_run = right_para.add_run('assistant@cicero.im')
        email_run.font.name = 'Times New Roman'
        email_run.font.size = Pt(14)
        email_run.font.bold = True
        email_run.font.color.rgb = RGBColor(0, 0, 238)  # Blue color for email link

        # === REGULAR PAGES HEADER (empty - no logo or email) ===
        header = section.header
        header_para = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        header_para.clear()  # Keep header empty for non-first pages

        # === FIRST PAGE FOOTER (empty - no footer on first page) ===
        first_footer = section.first_page_footer
        if first_footer.paragraphs:
            for para in first_footer.paragraphs:
                para.clear()

        # === REGULAR PAGES FOOTER (with Cicero Assistant and website) ===
        footer = section.footer
        footer_para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        footer_para.clear()

        # Create a table for footer layout
        if not footer.tables:
            footer_table = footer.add_table(rows=1, cols=2, width=table_width)
            footer_table.autofit = False
            footer_table.columns[0].width = int(table_width * 0.6)  # 60% for "Cicero Assistant"
            footer_table.columns[1].width = int(table_width * 0.4)  # 40% for website
        else:
            footer_table = footer.tables[0]

        # Remove table borders
        for row in footer_table.rows:
            for cell in row.cells:
                tc = cell._element
                tcPr = tc.get_or_add_tcPr()
                tcBorders = OxmlElement('w:tcBorders')
                for border_name in ['top', 'left', 'bottom', 'right']:
                    border = OxmlElement(f'w:{border_name}')
                    border.set(qn('w:val'), 'nil')
                    tcBorders.append(border)
                tcPr.append(tcBorders)

        # Left cell: Cicero Assistant
        left_cell = footer_table.rows[0].cells[0]
        left_para = left_cell.paragraphs[0] if left_cell.paragraphs else left_cell.add_paragraph()
        left_para.clear()
        left_para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

        left_run = left_para.add_run('Cicero Assistant')
        left_run.font.name = 'Times New Roman'
        left_run.font.size = Pt(10)
        left_run.font.bold = True
        left_run.font.color.rgb = RGBColor(0, 0, 0)

        # Right cell: Website
        right_cell = footer_table.rows[0].cells[1]
        right_para = right_cell.paragraphs[0] if right_cell.paragraphs else right_cell.add_paragraph()
        right_para.clear()
        right_para.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

        website_run = right_para.add_run('www.cicero.im')
        website_run.font.name = 'Times New Roman'
        website_run.font.size = Pt(10)
        website_run.font.bold = True
        website_run.font.color.rgb = RGBColor(0, 0, 238)  # Blue for link


def _add_docx_centered_division(doc: DocumentType) -> None:
    """Add the centered text division at the end of the document."""
    # Add a line separator
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(24)
    para.paragraph_format.space_after = Pt(12)
    para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

    # Add a horizontal line
    # We'll add it as a bottom border to an empty paragraph
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '4')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), 'auto')
    pBdr.append(bottom)
    para._p.get_or_add_pPr().append(pBdr)

    # Add first line: "Cicero, draft, modify, research. Will do."
    para1 = doc.add_paragraph()
    para1.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    para1.paragraph_format.space_after = Pt(6)

    run1 = para1.add_run('Cicero: please draft, modify, research. ')
    run1.font.name = 'Times New Roman'
    run1.font.size = Pt(12)
    run1.font.color.rgb = RGBColor(0, 0, 0)

    run2 = para1.add_run('Will do.')
    run2.font.name = 'Times New Roman'
    run2.font.size = Pt(12)
    run2.font.italic = True
    run2.font.color.rgb = RGBColor(0, 0, 0)

    # Add asterisks line
    para2 = doc.add_paragraph('***')
    para2.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    para2.paragraph_format.space_after = Pt(6)
    for run in para2.runs:
        run.font.name = 'Times New Roman'
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0, 0, 0)

    # Add last line: "Cícero, o seu melhor estagiário"
    para3 = doc.add_paragraph()
    para3.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    para3.paragraph_format.space_after = Pt(12)

    run3 = para3.add_run('Cícero: ')
    run3.font.name = 'Times New Roman'
    run3.font.size = Pt(12)
    run3.font.color.rgb = RGBColor(0, 0, 0)

    run4 = para3.add_run('o seu melhor estagiário')
    run4.font.name = 'Times New Roman'
    run4.font.size = Pt(12)
    run4.font.italic = True
    run4.font.color.rgb = RGBColor(0, 0, 0)
