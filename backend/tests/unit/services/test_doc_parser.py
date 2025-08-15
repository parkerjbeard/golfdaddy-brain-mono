"""
Unit tests for documentation parser service.
"""

import tempfile
from pathlib import Path

import pytest

from app.services.doc_parser import DocChunk, MarkdownParser


class TestDocChunk:
    """Test DocChunk dataclass."""

    def test_chunk_creation(self):
        """Test creating a DocChunk."""
        chunk = DocChunk(
            heading="Introduction",
            content="This is the introduction content.",
            order_key=0,
            level=1,
            metadata={"author": "test"},
            code_blocks=[{"language": "python", "code": "print('hello')"}],
        )

        assert chunk.heading == "Introduction"
        assert chunk.order_key == 0
        assert chunk.level == 1
        assert chunk.metadata["author"] == "test"
        assert len(chunk.code_blocks) == 1


class TestMarkdownParser:
    """Test Markdown parser."""

    def test_parse_simple_markdown(self):
        """Test parsing simple Markdown content."""
        parser = MarkdownParser()

        # Create a temporary Markdown file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """# Title

This is a paragraph.

## Section 1

Content for section 1.

## Section 2

Content for section 2.
"""
            )
            temp_path = Path(f.name)

        try:
            front_matter, chunks = parser.parse_file(temp_path)

            assert len(chunks) > 0

            # Check first chunk (Title)
            title_chunk = next((c for c in chunks if c.heading == "Title"), None)
            assert title_chunk is not None
            assert title_chunk.level == 1
            assert "This is a paragraph" in title_chunk.content

            # Check sections
            section1 = next((c for c in chunks if c.heading == "Section 1"), None)
            assert section1 is not None
            assert section1.level == 2
            assert "Content for section 1" in section1.content

        finally:
            temp_path.unlink()

    def test_parse_with_front_matter(self):
        """Test parsing Markdown with front matter."""
        parser = MarkdownParser()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """---
title: Test Document
author: Test Author
tags: [test, documentation]
---

# Main Content

This is the main content.
"""
            )
            temp_path = Path(f.name)

        try:
            front_matter, chunks = parser.parse_file(temp_path)

            # Check front matter
            assert front_matter["title"] == "Test Document"
            assert front_matter["author"] == "Test Author"
            assert "test" in front_matter["tags"]

            # Check content
            assert len(chunks) > 0
            main_chunk = chunks[0]
            assert "Main Content" in main_chunk.heading

        finally:
            temp_path.unlink()

    def test_parse_with_code_blocks(self):
        """Test parsing Markdown with code blocks."""
        parser = MarkdownParser()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """# Code Examples

Here's a Python example:

```python
def hello():
    print("Hello, World!")
```

And a JavaScript example:

```javascript
function greet() {
    console.log("Hello!");
}
```
"""
            )
            temp_path = Path(f.name)

        try:
            front_matter, chunks = parser.parse_file(temp_path)

            assert len(chunks) > 0
            chunk = chunks[0]

            # Check that code blocks were extracted
            assert len(chunk.code_blocks) >= 2

            # Check Python code block
            python_block = next((b for b in chunk.code_blocks if b["language"] == "python"), None)
            assert python_block is not None
            assert "def hello()" in python_block["code"]

            # Check JavaScript code block
            js_block = next((b for b in chunk.code_blocks if b["language"] == "javascript"), None)
            assert js_block is not None
            assert "function greet()" in js_block["code"]

        finally:
            temp_path.unlink()

    def test_chunk_by_headings(self):
        """Test chunking by heading hierarchy."""
        parser = MarkdownParser()

        content = """# Level 1

Content under level 1.

## Level 2A

Content under 2A.

### Level 3

Nested content.

## Level 2B

Content under 2B.
"""

        chunks = parser._chunk_by_headings(content)

        # Should create chunks for each heading
        assert len(chunks) >= 4

        # Check heading levels
        level1 = next((c for c in chunks if c.heading == "Level 1"), None)
        assert level1 is not None
        assert level1.level == 1

        level2a = next((c for c in chunks if c.heading == "Level 2A"), None)
        assert level2a is not None
        assert level2a.level == 2

        level3 = next((c for c in chunks if c.heading == "Level 3"), None)
        assert level3 is not None
        assert level3.level == 3

        # Check order keys are sequential
        order_keys = [c.order_key for c in chunks]
        assert order_keys == sorted(order_keys)

    def test_extract_links(self):
        """Test extracting links from Markdown."""
        parser = MarkdownParser()

        content = """
Here's an [inline link](https://example.com).

And a [reference link][ref1].

[ref1]: https://reference.com "Reference"
"""

        links = parser.extract_links(content)

        assert len(links) >= 2

        # Check inline link
        inline_link = next((l for l in links if l["text"] == "inline link"), None)
        assert inline_link is not None
        assert inline_link["url"] == "https://example.com"

        # Check reference link
        ref_link = next((l for l in links if l["text"] == "reference link"), None)
        assert ref_link is not None
        assert ref_link["url"] == 'https://reference.com "Reference"'

    def test_extract_code_blocks(self):
        """Test extracting code blocks."""
        parser = MarkdownParser()

        content = """
```python
def test():
    pass
```

    Indented code block
    with multiple lines

```
No language specified
```
"""

        code_blocks = parser.extract_code_blocks(content)

        assert len(code_blocks) >= 2

        # Check Python block
        python_block = next((b for b in code_blocks if b["language"] == "python"), None)
        assert python_block is not None
        assert "def test()" in python_block["code"]

        # Check block without language
        text_blocks = [b for b in code_blocks if b["language"] == "text"]
        assert len(text_blocks) >= 1

    def test_update_code_snippets(self):
        """Test updating code snippets in Markdown."""
        parser = MarkdownParser()

        original = """# Example

```python
old_code = "old"
```

Some text.
"""

        updates = {'old_code = "old"': 'new_code = "new"'}

        updated = parser.update_code_snippets(original, updates)

        assert 'new_code = "new"' in updated
        assert 'old_code = "old"' not in updated
        assert "Some text." in updated  # Other content preserved

    def test_parse_empty_file(self):
        """Test parsing an empty Markdown file."""
        parser = MarkdownParser()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("")
            temp_path = Path(f.name)

        try:
            front_matter, chunks = parser.parse_file(temp_path)

            assert front_matter == {}
            assert chunks == []

        finally:
            temp_path.unlink()

    def test_parse_invalid_file(self):
        """Test parsing a non-existent file."""
        parser = MarkdownParser()

        front_matter, chunks = parser.parse_file(Path("/nonexistent/file.md"))

        # Should handle error gracefully
        assert front_matter == {}
        assert chunks == []
