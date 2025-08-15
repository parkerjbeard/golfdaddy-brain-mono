"""
Markdown documentation parser for chunking and indexing.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import frontmatter
from markdown_it import MarkdownIt

logger = logging.getLogger(__name__)


@dataclass
class DocChunk:
    """Represents a parsed documentation chunk."""

    heading: str
    content: str
    order_key: int
    level: int
    metadata: Dict[str, Any] = None
    code_blocks: List[Dict[str, str]] = None


class MarkdownParser:
    """Parser for Markdown documentation files."""

    def __init__(self):
        """Initialize the Markdown parser."""
        self.md = MarkdownIt()

    def parse_file(self, file_path: Path) -> Tuple[Dict[str, Any], List[DocChunk]]:
        """Parse a Markdown file and extract structured chunks.

        Returns:
            Tuple of (front_matter, chunks)
        """
        try:
            # Read file content
            content = file_path.read_text(encoding="utf-8")

            # Extract front matter
            post = frontmatter.loads(content)
            front_matter = post.metadata
            markdown_content = post.content

            # Parse and chunk the content
            chunks = self._chunk_by_headings(markdown_content)

            return front_matter, chunks

        except Exception as e:
            logger.error(f"Error parsing Markdown file {file_path}: {e}")
            return {}, []

    def _chunk_by_headings(self, content: str) -> List[DocChunk]:
        """Chunk content by heading hierarchy."""
        chunks = []
        tokens = self.md.parse(content)

        current_chunk = None
        current_content = []
        order_key = 0

        for i, token in enumerate(tokens):
            if token.type == "heading_open":
                # Save previous chunk if exists
                if current_chunk:
                    current_chunk.content = self._render_content(current_content)
                    current_chunk.code_blocks = self.extract_code_blocks(current_chunk.content)
                    chunks.append(current_chunk)

                # Start new chunk
                level = int(token.tag[1])  # h1 -> 1, h2 -> 2, etc.
                heading_text = ""

                # Find the heading text
                j = i + 1
                while j < len(tokens) and tokens[j].type != "heading_close":
                    if tokens[j].type == "inline":
                        heading_text = tokens[j].content
                    j += 1

                current_chunk = DocChunk(
                    heading=heading_text, content="", order_key=order_key, level=level, metadata={}, code_blocks=[]
                )
                current_content = []
                order_key += 1

            elif token.type == "inline" and current_chunk:
                current_content.append(token.content)
            elif token.type == "fence" and current_chunk:
                # Preserve code blocks
                current_content.append(f"```{token.info}\n{token.content}```")

        # Save last chunk
        if current_chunk:
            current_chunk.content = self._render_content(current_content)
            current_chunk.code_blocks = self.extract_code_blocks(current_chunk.content)
            chunks.append(current_chunk)

        # If no headings, treat entire content as single chunk
        if not chunks and content.strip():
            chunks.append(
                DocChunk(
                    heading="Document",
                    content=content,
                    order_key=0,
                    level=0,
                    metadata={},
                    code_blocks=self.extract_code_blocks(content),
                )
            )

        return chunks

    def _render_content(self, content_parts: List[str]) -> str:
        """Render content parts into a string."""
        return "\n".join(content_parts).strip()

    def extract_code_blocks(self, content: str) -> List[Dict[str, str]]:
        """Extract code blocks from Markdown content."""
        code_blocks = []

        # Match fenced code blocks
        pattern = r"```(\w*)\n(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)

        for language, code in matches:
            code_blocks.append({"language": language or "text", "code": code.strip()})

        return code_blocks

    def extract_links(self, content: str) -> List[Dict[str, str]]:
        """Extract links from Markdown content."""
        links = []

        # Match inline links [text](url)
        inline_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        for text, url in re.findall(inline_pattern, content):
            links.append({"text": text, "url": url})

        # Match reference links [text][ref]
        ref_pattern = r"\[([^\]]+)\]\[([^\]]+)\]"
        ref_definitions = r"^\[([^\]]+)\]:\s*(.+)$"

        refs = {}
        for ref_id, url in re.findall(ref_definitions, content, re.MULTILINE):
            refs[ref_id] = url

        for text, ref_id in re.findall(ref_pattern, content):
            if ref_id in refs:
                links.append({"text": text, "url": refs[ref_id]})

        return links

    def extract_images(self, content: str) -> List[Dict[str, str]]:
        """Extract images from Markdown content."""
        images = []

        # Match images ![alt](url)
        pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        for alt, url in re.findall(pattern, content):
            images.append({"alt": alt, "url": url})

        return images

    def extract_tables(self, content: str) -> List[str]:
        """Extract tables from Markdown content."""
        tables = []

        # Simple table detection (lines with pipes)
        lines = content.split("\n")
        in_table = False
        current_table = []

        for line in lines:
            if "|" in line:
                in_table = True
                current_table.append(line)
            elif in_table:
                # Table ended
                if current_table:
                    tables.append("\n".join(current_table))
                    current_table = []
                in_table = False

        # Don't forget last table
        if current_table:
            tables.append("\n".join(current_table))

        return tables

    def extract_metadata(self, content: str) -> Dict[str, Any]:
        """Extract metadata from content (like tags, categories)."""
        metadata = {}

        # Extract hashtags
        hashtags = re.findall(r"#(\w+)", content)
        if hashtags:
            metadata["tags"] = list(set(hashtags))

        # Extract mentioned files
        files = re.findall(r"`([^`]+\.\w+)`", content)
        if files:
            metadata["mentioned_files"] = list(set(files))

        return metadata

    def update_code_snippets(self, content: str, updates: Dict[str, str]) -> str:
        """Update code snippets in Markdown content."""
        updated = content

        for old_code, new_code in updates.items():
            # Try to match in fenced code blocks
            pattern = re.compile(r"(```\w*\n)" + re.escape(old_code) + r"(\n```)", re.DOTALL)
            updated = pattern.sub(r"\1" + new_code + r"\2", updated)

        return updated
