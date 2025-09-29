from __future__ import annotations

import asyncio
import base64
import datetime
import email
import email.utils
import io
import os
import quopri
import re
import socket
import uuid
from email.header import decode_header
from email.headerregistry import Address
from email.message import (
    EmailMessage,
    Message,  # For type hinting email_message
)
from email.utils import format_datetime, make_msgid
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo

import aiosmtplib
import markitdown
from docling.document_converter import DocumentConverter
from docling_core.types.io import DocumentStream
from src.cicero_mail_pydantic_ptbr.config.constants import (
    ARCHIVE_EMAIL,
    ATTACHMENT_PROCESSING_ERROR_MSG_TEMPLATE,
    DOMAIN,
    SMTP_NAME,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SERVER,
    SMTP_USE_TLS,
    SMTP_USERNAME,
    SUPPORTED_ATTACHMENT_EXTENSIONS,
)
from src.cicero_mail_pydantic_ptbr.models.error_types import EmailDecodingError
from src.cicero_mail_pydantic_ptbr.models.request_types import generate_json_safe_id
from src.cicero_mail_pydantic_ptbr.utils.custom_logging import logger
from src.cicero_mail_pydantic_ptbr.utils.datetime_format import get_serialized_nyc_now


def sanitize_filename(filename: str) -> str:
    """Securely sanitize filename to prevent path traversal and ensure safe characters.

    Args:
        filename: Original filename to sanitize

    Returns:
        str: Sanitized filename with path traversal patterns removed

    """
    if not filename:
        return 'unnamed_file'

    # Remove any directory traversal patterns like "../" or "..\"
    # Replace with empty string to completely remove them
    filename = re.sub(r'\.\.\/', '', filename)
    filename = re.sub(r'\.\\', '', filename)

    # Remove any path separators to prevent directory traversal
    filename = re.sub(r'[\/\\]', '', filename)

    # Only allow safe characters: alphanumeric, dots, hyphens, underscores
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

    # Consolidate multiple underscores to prevent attempts to obfuscate
    filename = re.sub(r'_{2,}', '_', filename)

    # Ensure filename is not empty after sanitization
    if not filename or filename in {'.', '..'}:
        return 'unnamed_file'

    # Limit filename length to prevent potential issues
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        # Preserve extension while limiting total length
        filename = name[: max_length - len(ext)] + ext

    return filename


async def extract_text_from_pdf(payload: bytes) -> str:
    """Extract text from PDF document and convert to markdown.

    First attempts with markitdown, falls back to Docling if that fails.

    Args:
        payload: PDF content as bytes

    Returns:
        str: Extracted text as markdown or error message if extraction fails

    """
    logger.warning('Here trying to get the pdf out')

    extracted_text = None

    # First attempt: Try markitdown
    try:
        # Create a new BytesIO stream (the previous one may have been consumed)
        buf = BytesIO(payload)
        source = DocumentStream(name='document.pdf', stream=buf)

        # Initialize DocumentConverter
        converter = DocumentConverter()

        # Run the conversion in a separate thread to avoid blocking
        result = await asyncio.to_thread(converter.convert, source)

        # Extract text from Docling result
        if result:
            # Try markdown rendering first
            if hasattr(result, 'document') and result.document:
                try:
                    markdown_content = await asyncio.to_thread(result.document.export_to_markdown)
                    if markdown_content and markdown_content.strip():
                        logger.info('Successfully extracted PDF using Docling fallback (markdown)')
                        extracted_text = markdown_content
                except Exception as e:
                    logger.warning(f'Docling markdown export failed: {e}')

            # If markdown didn't work, try plain text
            if not extracted_text and hasattr(result, 'document') and result.document:
                try:
                    # Try to get text from document elements
                    # Check if document has a method to extract text content
                    if hasattr(result.document, 'export_to_text'):
                        doc_text = await asyncio.to_thread(result.document.export_to_text)
                        if doc_text and doc_text.strip():
                            logger.info('Successfully extracted PDF using Docling fallback (text)')
                            extracted_text = doc_text
                except Exception:
                    # If that doesn't work, try alternative approaches
                    pass

    except Exception as e:
        logger.error(f'Docling also failed to extract PDF text: {e}', exc_info=True)

    # If markitdown didn't succeed, try Docling fallback
    if not extracted_text:
        try:
            # Initialize MarkItDown with plugins enabled for better extraction
            markitdown_converter = markitdown.MarkItDown(enable_plugins=True)

            # Create binary stream from payload
            pdf_stream = BytesIO(payload)

            # Run the synchronous convert_stream method in a separate thread
            result = await asyncio.to_thread(markitdown_converter.convert_stream, pdf_stream)

            # Check if we got valid content
            if result and result.text_content and result.text_content.strip():
                logger.info('Successfully extracted PDF using markitdown')
                extracted_text = result.text_content
            else:
                logger.warning('Markitdown returned empty or invalid content')

        except Exception as e:
            logger.warning(f'Markitdown failed to extract PDF text: {e}')

    # Return the extracted text or error message
    return extracted_text or ATTACHMENT_PROCESSING_ERROR_MSG_TEMPLATE


async def extract_text_from_docx(payload: bytes) -> str:
    """Extract text from DOCX document and convert to markdown, including comments.

    First attempts with markitdown, falls back to Docling if that fails.

    Args:
        payload: DOCX content as bytes

    Returns:
        str: Extracted text as markdown or error message if extraction fails

    """
    extracted_text = None

    # First attempt: Try markitdown
    try:
        buf = BytesIO(payload)
        source = DocumentStream(name='document.docx', stream=buf)

        # Initialize DocumentConverter
        converter = DocumentConverter()

        # Run the conversion in a separate thread to avoid blocking
        result = await asyncio.to_thread(converter.convert, source)

        # Extract text from Docling result
        if result:
            # Try markdown rendering first
            if hasattr(result, 'document') and result.document:
                try:
                    markdown_content = await asyncio.to_thread(result.document.export_to_markdown)
                    if markdown_content and markdown_content.strip():
                        logger.info('Successfully extracted DOCX using Docling fallback (markdown)')
                        extracted_text = markdown_content
                except Exception as e:
                    logger.warning(f'Docling markdown export failed: {e}')

                # If markdown didn't work, try plain text
            if not extracted_text and hasattr(result, 'document') and result.document:
                try:
                    # Try to get text from document elements
                    if hasattr(result.document, 'export_to_text'):
                        doc_text = await asyncio.to_thread(result.document.export_to_text)
                        if doc_text and doc_text.strip():
                            logger.info('Successfully extracted DOCX using Docling fallback (text)')
                            extracted_text = doc_text
                except Exception:
                    # If that doesn't work, try alternative approaches
                    pass

    except Exception as e:
        logger.error(f'Docling also failed to extract DOCX text: {e}', exc_info=True)

    # If markitdown didn't succeed, try Docling fallback
    if not extracted_text:
        try:
            # Initialize MarkItDown with plugins enabled and style_map for comments
            markitdown_converter = markitdown.MarkItDown(enable_plugins=True, style_map='comment-reference => ')

            # Create binary stream from payload
            docx_stream = BytesIO(payload)

            # Run the synchronous convert_stream method in a separate thread
            result = await asyncio.to_thread(markitdown_converter.convert_stream, docx_stream)

            # Check if we got valid content
            if result and result.text_content and result.text_content.strip():
                logger.info('Successfully extracted DOCX using markitdown')
                extracted_text = result.text_content
            else:
                logger.warning('Markitdown returned empty or invalid content')

        except Exception as e:
            logger.warning(f'Markitdown failed to extract DOCX text: {e}')

    # Return the extracted text or error message
    return extracted_text or ATTACHMENT_PROCESSING_ERROR_MSG_TEMPLATE


async def process_headers(email_message) -> dict:
    """Process email headers with proper decoding.

    Args:
        email_message: Email message object

    Returns:
        dict: Processed headers

    Raises:
        EmailProcessingError: If processing fails

    """
    headers = {}

    # Standard RFC 5322 headers with variations
    header_mappings = {
        'from': ['from', 'sender', 'reply-to'],
        'to': ['to', 'delivered-to', 'envelope-to'],
        'cc': ['cc', 'carbon-copy'],
        'bcc': ['bcc', 'blind-carbon-copy'],
        'subject': ['subject'],
        'date': ['date', 'delivery-date', 'orig-date'],
        'message-id': ['message-id'],
        'in-reply-to': ['in-reply-to'],
        'references': ['references'],
    }

    try:
        # Process each header group
        for standard_key, variations in header_mappings.items():
            for header in variations:
                raw_value = email_message.get(header)
                if raw_value:
                    try:
                        if standard_key == 'date':
                            headers[standard_key] = await parse_date(raw_value)
                        elif standard_key in {'from', 'to', 'cc', 'bcc'}:
                            # Parse email addresses
                            addresses = email.utils.getaddresses([raw_value])
                            if addresses:
                                headers[standard_key] = [
                                    {
                                        'name': decode_header_value(name) if name else '',
                                        'email': addr.lower() if addr else '',
                                    }
                                    for name, addr in addresses
                                ]
                        else:
                            # Decode any encoded headers
                            headers[standard_key] = decode_header_value(raw_value)
                        break  # Stop after first successful decode
                    except Exception as e:
                        logger.warning(f'Failed to process header {header}: {e}')
                        continue

        return headers

    except Exception as e:
        logger.exception(f'Header processing failed: {e}')
        return {}


def decode_header_value(header_value: str | bytes) -> str:
    """Decode email header with proper handling of encoded words.

    Args:
        header_value: Raw header value

    Returns:
        str: Decoded header text

    """
    if not header_value:
        return ''

    try:
        # Convert bytes to string for decode_header
        if isinstance(header_value, bytes):
            header_value = header_value.decode('ascii', errors='replace')

        # Handle RFC 2047 encoded words
        decoded_parts = []
        for part, charset in decode_header(header_value):
            if isinstance(part, bytes):
                try:
                    if charset:
                        decoded_parts.append(part.decode(charset))
                    else:
                        # Try common encodings
                        for encoding in ['utf-8', 'latin1', 'iso-8859-1']:
                            try:
                                decoded_parts.append(part.decode(encoding))
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            # If all fails, use replace
                            decoded_parts.append(part.decode('utf-8', errors='replace'))
                except Exception:
                    decoded_parts.append(part.decode('utf-8', errors='replace'))
            else:
                decoded_parts.append(str(part))

        return ' '.join(decoded_parts)
    except Exception as e:
        logger.warning(f'Header decode failed: {e}')
        # Fallback: return as-is with replacement chars
        if isinstance(header_value, bytes):
            return header_value.decode('utf-8', errors='replace')
        return str(header_value)


async def decode_text_payload(payload: bytes, charset: str | None = None) -> str:
    """Decode text payload with fallbacks.

    Args:
        payload: Raw payload bytes
        charset: Original charset if specified

    Returns:
        str: Decoded text content

    """
    if not payload:
        return ''

    # Try original charset first
    if charset:
        try:
            return payload.decode(charset)
        except UnicodeDecodeError:
            pass

    # Try common encodings
    for encoding in ['utf-8', 'latin1', 'iso-8859-1', 'cp1252', 'ascii']:
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue

    # Last resort: decode with replacement
    return payload.decode('utf-8', errors='replace')


async def decode_content(
    content: bytes, content_type: str | None = None, transfer_encoding: str | None = None
) -> tuple[str, str]:
    """Decode email content with multiple fallback options.

    Args:
        content: Raw content bytes
        content_type: Content-Type header value
        transfer_encoding: Content-Transfer-Encoding header value

    Returns:
        tuple: (decoded_content: str, encoding_used: str)

    Raises:
        EmailDecodingError: If all decoding attempts fail

    """
    # Extract charset from content-type if present
    charset = None
    if content_type and 'charset=' in content_type.lower():
        charset = content_type.lower().split('charset=')[1].split(';')[0].strip('"\'')

    # Define fallback encodings
    encodings = [
        ('base64_utf8', lambda x: base64.b64decode(x).decode('utf-8')),
        ('base64_latin1', lambda x: base64.b64decode(x).decode('latin-1')),
        ('quoted_printable_utf8', lambda x: quopri.decodestring(x).decode('utf-8')),
        ('utf8', lambda x: x.decode('utf-8')),
        ('latin1', lambda x: x.decode('latin-1')),
        ('ascii', lambda x: x.decode('ascii')),
    ]

    # Try specified charset first if present
    if charset:
        try:
            return content.decode(charset), f'specified_{charset}'
        except UnicodeDecodeError:
            pass

    # Check transfer encoding
    if transfer_encoding:
        if 'base64' in transfer_encoding.lower():
            try:
                return base64.b64decode(content).decode('utf-8'), 'base64_utf8'
            except (ValueError, UnicodeDecodeError):
                pass
        elif 'quoted-printable' in transfer_encoding.lower():
            try:
                return quopri.decodestring(content).decode('utf-8'), 'quoted_printable_utf8'
            except UnicodeDecodeError:
                pass

    # Try all encodings
    errors = []
    for name, decoder in encodings:
        try:
            result = decoder(content)
            return result, name
        except Exception as e:
            errors.append(f'{name}: {e!s}')
            continue

    # If all fail, try fallback charsets with replacement
    fallback_charsets = [charset or 'utf-8', 'utf-8', 'latin1', 'iso-8859-1', 'cp1252', 'ascii']

    for fallback in fallback_charsets:
        try:
            return content.decode(fallback, errors='replace'), f'{fallback}_replace'
        except Exception as e:
            errors.append(f'{fallback}_replace: {e!s}')

    # If everything fails, raise error with details
    msg = f'All decoding attempts failed: {"; ".join(errors)}'
    raise EmailDecodingError(msg)


async def parse_date(date_str: str) -> str:
    """Parse email date with fallbacks.

    Args:
        date_str: Date string from email header

    Returns:
        str: Parsed date string or default value if parsing fails

    """
    if date_str is not None:
        return date_str
    return 'ugabuga'


# --- Main Processing Function ---
async def process_normal_message(email_message: Message, msg_id: str) -> dict[str, Any]:
    """Process a normal email message with proper content handling.

    Attachments are stored as a list of tuples:
    (original_filename, payload_bytes_or_None, markdown_content_or_status_str).
    """
    try:
        headers = await process_headers(email_message)

        sender_list = headers.get('from', [])
        sender = sender_list[0] if sender_list else {'name': '', 'email': 'unknown@example.com'}

        recipient_list = headers.get('to', [])
        recipient = recipient_list[0] if recipient_list else {'name': '', 'email': 'unknown@example.com'}

        cc_list = headers.get('cc', [])

        parsed_data: dict[str, Any] = {
            'id': await generate_json_safe_id(),
            'imap_uid': msg_id,
            'sender': sender,
            'sender_name': sender.get('name', ''),
            'sender_address': sender.get('email', 'unknown@example.com'),
            'recipient': recipient,
            'recipient_name': recipient.get('name', ''),
            'recipient_address': recipient.get('email', 'unknown@example.com'),
            'cc': cc_list,
            'subject': str(headers.get('subject', '(No Subject)')),
            'date': get_serialized_nyc_now(),
            'message_id': str(headers.get('message-id', '')),
            'references': str(headers.get('references', '')),
            'in_reply_to': str(headers.get('in-reply-to', '')),
            'body': '',
            'attachments': {},
        }

        logger.info(
            "Processing email: From=%s, To=%s, Subject='%s', Message-ID=%s",
            parsed_data['sender_address'],
            parsed_data['recipient_address'],
            parsed_data['subject'],
            parsed_data['message_id'],
        )
        try:
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get('Content-Disposition', '')).lower()

                # Skip image content types
                if content_type.startswith('image/'):
                    logger.debug(f'Skipping image content: {content_type}')
                    continue

                if content_type == 'text/plain' and 'attachment' not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload and isinstance(payload, bytes):
                            decoded_text = await decode_text_payload(payload, part.get_content_charset())
                            if parsed_data['body']:
                                parsed_data['body'] += '\n\n' + decoded_text
                            else:
                                parsed_data['body'] = decoded_text
                        elif payload and isinstance(payload, str):
                            # If payload is already a string, use it directly
                            if parsed_data['body']:
                                parsed_data['body'] += '\n\n' + payload
                            else:
                                parsed_data['body'] = payload
                    except Exception as e:
                        logger.warning(f'Failed to decode text payload: {e}', exc_info=True)

                elif (
                    content_type == 'text/html' and 'attachment' not in content_disposition and not parsed_data['body']
                ):
                    # Only use HTML if we don't have plain text
                    try:
                        payload = part.get_payload(decode=True)
                        if payload and isinstance(payload, bytes):
                            # Option 1: Store raw HTML (as in original code)
                            decoded_html = await decode_text_payload(payload, part.get_content_charset())
                            parsed_data['body'] = decoded_html

                            # Option 2: Convert HTML to Markdown (if desired for consistency)
                            html_charset = part.get_content_charset() or 'utf-8'
                            html_bytes = (await decode_text_payload(payload, part.get_content_charset())).encode(
                                html_charset
                            )
                            markitdown_converter = markitdown.MarkItDown()
                            html_stream_info = markitdown.StreamInfo(mimetype='text/html', charset=html_charset)
                            result = await asyncio.to_thread(
                                markitdown_converter.convert_stream,
                                io.BytesIO(html_bytes),
                                stream_info=html_stream_info,
                            )
                            parsed_data['body'] = result.text_content
                        elif payload and isinstance(payload, str):
                            # If payload is already a string, use it directly
                            parsed_data['body'] = payload
                    except Exception as e:
                        logger.warning(f'Failed to decode HTML payload: {e}', exc_info=True)

                # Handle attachments
                elif 'attachment' in content_disposition:
                    filename = part.get_filename()
                    if not filename:
                        logger.debug('Skipping attachment with no filename.')
                        continue

                    # Normalize filename early for use in error messages too
                    base_name_orig, file_ext_orig = os.path.splitext(filename)
                    file_ext = file_ext_orig.lower()

                    # Sanitize normalized_filename components using secure function
                    sanitized_base_name = sanitize_filename(base_name_orig)

                    normalized_filename = sanitized_base_name
                    # The extension is already safe as it comes from the split from os.path.splitext
                    # We don't need to sanitize the extension separately since it's derived from the original filename
                    if file_ext:
                        normalized_filename = f'{sanitized_base_name}{file_ext}'

                    if file_ext not in SUPPORTED_ATTACHMENT_EXTENSIONS:
                        logger.info(f'Skipping unsupported attachment: {filename} (type: {file_ext})')
                        continue

                    logger.info(f'Processing attachment: {filename} (normalized: {normalized_filename})')
                    try:
                        payload = part.get_payload(decode=True)
                        if not payload:
                            logger.warning(f'Attachment {filename} has no payload.')
                            parsed_data['attachments'][normalized_filename] = (
                                f'# *ATTENTION!*\nAttachment {filename} is empty.'
                            )
                            continue

                        markdown_content = ''
                        try:
                            if isinstance(payload, bytes):
                                if file_ext == '.txt':
                                    markitdown_converter = markitdown.MarkItDown()
                                    # CRITICAL FIX: Added await here
                                    result = await asyncio.to_thread(
                                        markitdown_converter.convert_stream,  # Removed ()
                                        io.BytesIO(payload),
                                        stream_info=markitdown.StreamInfo(
                                            extension='.txt', mimetype='text/plain', charset=part.get_content_charset()
                                        ),
                                    )
                                    markdown_content = result.text_content
                                elif file_ext == '.pdf':
                                    markdown_content = await extract_text_from_pdf(payload)
                                elif file_ext == '.docx':
                                    markdown_content = await extract_text_from_docx(payload)
                                else:
                                    # For other file extensions, return an error message
                                    markdown_content = ATTACHMENT_PROCESSING_ERROR_MSG_TEMPLATE.format(
                                        filename=filename
                                    )
                            else:
                                # If payload is not bytes, we can't process it with these functions
                                markdown_content = ATTACHMENT_PROCESSING_ERROR_MSG_TEMPLATE.format(filename=filename)
                        except Exception as e_convert:
                            logger.warning(f'Error converting {filename} to markdown: {e_convert}', exc_info=True)
                            markdown_content = ATTACHMENT_PROCESSING_ERROR_MSG_TEMPLATE.format(filename=filename)

                        parsed_data['attachments'][normalized_filename] = markdown_content
                        logger.info(f'Successfully processed attachment: {filename} -> {normalized_filename}')

                    except Exception as e_process:
                        logger.warning(f'Could not process attachment {filename}: {e_process}', exc_info=True)
                        error_message = ATTACHMENT_PROCESSING_ERROR_MSG_TEMPLATE.format(filename=filename)
                        parsed_data['attachments'][normalized_filename] = error_message
                        # The continue here might be implicit due to the loop structure

                elif content_disposition:  # Avoid logging for multipart containers themselves
                    logger.debug(f'Skipping unhandled part: {content_type}, Disposition: {content_disposition}')
                elif not part.is_multipart():  # Avoid logging multipart containers
                    logger.debug(f'Skipping unhandled simple part: {content_type}')

                # Final logging of processed message
                logger.info(
                    'Completed processing email: {} attachments, Body length: {} chars',
                    len(parsed_data['attachments']),
                    len(parsed_data.get('body', '')),  # Use .get for body in case it was never set
                )
            return parsed_data
        except Exception as e:
            logger.error(f'Error processing email: {e}')
            raise
    except Exception as e:
        logger.error(f'Error processing email: {e}')
        raise


async def send_async(
    sent_email_recipient_username_with_domain: str,
    sent_email_subject: str,
    sent_email_plain_body: str,
    sent_email_recipient_realname: str = '',
    sent_email_cc: str | list[str] | None = None,
    sent_email_bcc: str | list[str] | None = None,
    sent_email_attachments: Any | None = None,
    sent_email_html_body: str | None = None,
    cicero_id: str | None = None,
    *,
    # New, RFC-compliant threading parameters:
    message_id: str | None = None,
    in_reply_to_message_id: str | None = None,
    references: list[str] | None = None,
    # Extra first-class custom headers:
    extra_headers: dict[str, str] | None = None,
    # Legacy parameters (kept for backward compatibility but deprecated)
    in_reply_to_unique_id: str | None = None,
) -> str:
    """Send an email asynchronously using aiosmtplib with automatic archiving.

    Sends an email and returns the Message-ID used.
    Always sets a valid 'Message-ID'. Optionally sets 'In-Reply-To' and 'References'.
    Adds 'X-Cicero-Request-Id' if cicero_id is provided.

    All outgoing emails are automatically BCC'd to the archive address for compliance.

    Args:
        sent_email_recipient_username_with_domain: Email address of the recipient
        sent_email_subject: Email subject
        sent_email_plain_body: Plain text email body
        sent_email_recipient_realname: Display name of the recipient
        sent_email_cc: Optional CC recipient(s)
        sent_email_bcc: Optional BCC recipient(s)
        sent_email_attachments: Optional list of attachments as tuples of (filename, content, mimetype)
        sent_email_html_body: Optional HTML version of the email body
        cicero_id: Optional ID to use as base for Message-ID
        message_id: Optional custom Message-ID (if not provided, one will be generated)
        in_reply_to_message_id: Optional Message-ID of the message being replied to
        references: Optional list of Message-IDs in the thread
        extra_headers: Optional dictionary of additional headers to set
        in_reply_to_unique_id: DEPRECATED - use in_reply_to_message_id instead

    Returns:
        The Message-ID of the sent email

    """
    # Create the message
    msg = EmailMessage()
    if sent_email_recipient_username_with_domain == 'estagiario@cicero.chat':
        return ''

    if sent_email_attachments and isinstance(sent_email_attachments, dict):
        sent_email_attachments = None

    # Generate a deterministic, unique Message-ID if not provided.
    # Format: <cicero.{cicero_id}.{uuid}@{hostname}>
    hostname = socket.getfqdn() or 'mail.local'
    if message_id is None:
        rand = uuid.uuid4().hex
        thread = str(cicero_id) if cicero_id is not None else 'noid'
        sent_email_id_with_msgid = f'<cicero.{thread}.{rand}@{hostname}>'
    else:
        sent_email_id_with_msgid = message_id

    # Get current time in New York timezone and format it properly
    sent_email_date = datetime.datetime.now().astimezone(ZoneInfo('America/New_York'))

    # Set headers
    msg['Message-ID'] = sent_email_id_with_msgid
    msg['Date'] = format_datetime(sent_email_date)  # Use email.utils.format_datetime
    msg['Subject'] = sent_email_subject
    msg['From'] = Address(display_name=SMTP_NAME, addr_spec=SMTP_USERNAME)
    msg['To'] = Address(
        display_name=sent_email_recipient_realname, addr_spec=sent_email_recipient_username_with_domain
    )

    # Set In-Reply-To if provided (new parameter takes precedence)
    reply_to_msg_id = in_reply_to_message_id or in_reply_to_unique_id
    if reply_to_msg_id:
        # If it's not already in message-id format, wrap it
        if not reply_to_msg_id.startswith('<') or not reply_to_msg_id.endswith('>'):
            reply_to_msg_id = make_msgid(idstring=reply_to_msg_id, domain=DOMAIN)
        msg['In-Reply-To'] = reply_to_msg_id

    # Set References if provided
    if references:
        msg['References'] = ' '.join(ref for ref in references if ref)
    elif reply_to_msg_id:
        # If no references provided but we have a reply-to, use that as references
        msg['References'] = reply_to_msg_id

    # Add Cicero Request ID header if provided
    if cicero_id is not None:
        msg['X-Cicero-Request-Id'] = str(cicero_id)

    # Add extra headers if provided
    if extra_headers:
        for header_name, header_value in extra_headers.items():
            if header_value is not None:
                msg[header_name] = header_value

    # Add CC if provided
    if sent_email_cc:
        if isinstance(sent_email_cc, list):
            msg['Cc'] = ', '.join(sent_email_cc)
        else:
            msg['Cc'] = sent_email_cc

    # Build BCC list, ensuring archive is included once
    bcc_list: list[str] = []
    if sent_email_bcc:
        bcc_list = sent_email_bcc if isinstance(sent_email_bcc, list) else [sent_email_bcc]
    if ARCHIVE_EMAIL not in {addr.strip().lower() for addr in bcc_list}:
        bcc_list.append(ARCHIVE_EMAIL)
    # IMPORTANT: Do NOT set 'Bcc' header to prevent exposing BCC recipients

    # Set content (plain text or HTML+text)
    if sent_email_html_body:
        # If we have HTML, set both plain text and HTML versions
        msg.set_content(sent_email_plain_body)
        msg.add_alternative(sent_email_html_body, subtype='html')
    else:
        # Just plain text
        msg.set_content(sent_email_plain_body)

    # Add attachments if provided
    if sent_email_attachments:
        for filename, content, mimetype in sent_email_attachments:
            maintype, subtype = mimetype.split('/', 1)
            msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    logger.info(f"Sending email to {sent_email_recipient_username_with_domain} with subject '{sent_email_subject}'")

    # Build the full recipient list for SMTP envelope
    recipients = [sent_email_recipient_username_with_domain]
    if sent_email_cc:
        cc_list = sent_email_cc if isinstance(sent_email_cc, list) else [sent_email_cc]
        recipients.extend(cc_list)
    recipients.extend(bcc_list)

    # Send the email
    result = await aiosmtplib.send(
        msg,
        recipients=recipients,
        hostname=SMTP_SERVER,
        port=SMTP_PORT,
        username=SMTP_USERNAME,
        password=SMTP_PASSWORD,
        start_tls=SMTP_USE_TLS,
    )

    logger.info(f'Email sent: {result}')
    # On success, return the Message-ID so callers can persist it.
    return sent_email_id_with_msgid
