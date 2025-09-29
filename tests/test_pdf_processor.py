import asyncio
import os
import tempfile

from redlines.utils.pdf_processor import PDFProcessor


def test_pdf_processor() -> None:
    """Test the PDFProcessor class functionality."""
    # Create a basic PDFProcessor instance
    processor = PDFProcessor()

    # Test markdown content
    markdown_content = """
# Test Document

This is a test document to verify the PDFProcessor functionality.

## Features Tested

- Headers
- Bold text **bold**
- Italic text *italic*
- Lists
  - Item 1
  - Item 2
- Code blocks
  ```python
  print("Hello, World!")
  ```

### Conclusion

The PDFProcessor should handle all these elements properly.
"""

    try:
        # Test markdown to PDF conversion
        pdf_bytes = asyncio.run(
            processor.markdown_to_pdf(markdown_content, cicero_request_id='TEST-001', include_request_id=True)
        )

        # Save the PDF to a temporary file to verify it's valid
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(pdf_bytes)
            temp_file_path = temp_file.name

        # Verify the file exists and has content
        assert os.path.exists(temp_file_path), 'PDF file was not created'
        assert os.path.getsize(temp_file_path) > 0, 'PDF file is empty'

        # Clean up
        os.unlink(temp_file_path)

        # Test HTML to PDF conversion
        html_content = '<h1>Test HTML</h1><p>This is a test HTML content.</p>'
        asyncio.run(processor.html_to_pdf(html_content, cicero_request_id='TEST-02', include_request_id=True))

        # Test batch conversion
        markdown_contents = [
            '# Document 1\nContent of document 1.',
            '# Document 2\nContent of document 2.',
            '# Document 3\nContent of document 3.',
        ]

        batch_results = asyncio.run(
            processor.batch_convert_to_pdf(
                markdown_contents, cicero_request_ids=['BATCH-001', 'BATCH-002', 'BATCH-003'], include_request_id=True
            )
        )

        for pdf_bytes in batch_results:
            pass

    except Exception:
        raise


if __name__ == '__main__':
    test_pdf_processor()
