"""
Multi-language code parser using Tree-sitter and LibCST.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import libcst as cst
import tree_sitter as ts
from libcst.metadata import MetadataWrapper

logger = logging.getLogger(__name__)


@dataclass
class CodeSymbol:
    """Represents a parsed code symbol."""

    name: str
    kind: str  # function, class, method, interface, type, etc.
    signature: Optional[str]
    docstring: Optional[str]
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    decorators: List[str] = None
    type_hints: Dict[str, str] = None
    language: str = None


class BaseLanguageParser:
    """Base class for language-specific parsers."""

    def parse_file(self, file_path: Path, content: str) -> List[CodeSymbol]:
        """Parse a file and extract symbols."""
        raise NotImplementedError


class PythonParser(BaseLanguageParser):
    """Python parser using LibCST for accurate parsing with preservation."""

    def parse_file(self, file_path: Path, content: str) -> List[CodeSymbol]:
        """Parse Python file and extract symbols with full metadata."""
        symbols = []

        try:
            # Parse with LibCST
            module = cst.parse_module(content)
            wrapper = MetadataWrapper(module)

            # Extract symbols
            extractor = PythonSymbolExtractor()
            wrapper.visit(extractor)
            symbols = extractor.symbols

            # Set language for all symbols
            for symbol in symbols:
                symbol.language = "python"

        except Exception as e:
            logger.error(f"Error parsing Python file {file_path}: {e}")

        return symbols


class PythonSymbolExtractor(cst.CSTVisitor):
    """LibCST visitor to extract Python symbols."""

    def __init__(self):
        self.symbols = []
        self.current_class = None

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        """Extract class definitions."""
        # Get docstring
        docstring = self._extract_docstring(node.body)

        # Get decorators
        decorators = [
            decorator.decorator.value if hasattr(decorator.decorator, "value") else str(decorator.decorator)
            for decorator in node.decorators
        ]

        # Get position info
        pos = node.body.body[0] if node.body.body else node

        symbol = CodeSymbol(
            name=node.name.value,
            kind="class",
            signature=self._build_class_signature(node),
            docstring=docstring,
            start_line=getattr(pos, "start_line", 0),
            end_line=getattr(pos, "end_line", 0),
            start_col=getattr(pos, "start_column", 0),
            end_col=getattr(pos, "end_column", 0),
            decorators=decorators,
        )

        self.symbols.append(symbol)
        self.current_class = node.name.value
        return True

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        """Reset current class context."""
        self.current_class = None

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        """Extract function and method definitions."""
        # Determine if this is a method or function
        kind = "method" if self.current_class else "function"

        # Get docstring
        docstring = self._extract_docstring(node.body)

        # Get decorators
        decorators = [
            decorator.decorator.value if hasattr(decorator.decorator, "value") else str(decorator.decorator)
            for decorator in node.decorators
        ]

        # Extract type hints
        type_hints = self._extract_type_hints(node)

        # Get position info
        pos = node.body.body[0] if node.body.body else node

        symbol = CodeSymbol(
            name=node.name.value,
            kind=kind,
            signature=self._build_function_signature(node),
            docstring=docstring,
            start_line=getattr(pos, "start_line", 0),
            end_line=getattr(pos, "end_line", 0),
            start_col=getattr(pos, "start_column", 0),
            end_col=getattr(pos, "end_column", 0),
            decorators=decorators,
            type_hints=type_hints,
        )

        self.symbols.append(symbol)
        return True

    def _extract_docstring(self, body: cst.IndentedBlock) -> Optional[str]:
        """Extract docstring from function or class body."""
        if not body.body:
            return None

        first_stmt = body.body[0]
        if isinstance(first_stmt, cst.SimpleStatementLine):
            for stmt in first_stmt.body:
                if isinstance(stmt, cst.Expr) and isinstance(stmt.value, cst.SimpleString):
                    # Remove quotes and clean up
                    docstring = stmt.value.value
                    if docstring.startswith('"""') or docstring.startswith("'''"):
                        docstring = docstring[3:-3]
                    elif docstring.startswith('"') or docstring.startswith("'"):
                        docstring = docstring[1:-1]
                    return docstring.strip()
        return None

    def _build_function_signature(self, node: cst.FunctionDef) -> str:
        """Build function signature string."""
        params = []
        for param in node.params.params:
            param_str = param.name.value
            if param.annotation:
                param_str += f": {param.annotation.annotation}"
            if param.default:
                param_str += f" = {param.default}"
            params.append(param_str)

        signature = f"def {node.name.value}({', '.join(params)})"
        if node.returns:
            signature += f" -> {node.returns.annotation}"

        return signature

    def _build_class_signature(self, node: cst.ClassDef) -> str:
        """Build class signature string."""
        bases = []
        for arg in node.bases:
            if isinstance(arg.value, cst.Name):
                bases.append(arg.value.value)

        if bases:
            return f"class {node.name.value}({', '.join(bases)})"
        return f"class {node.name.value}"

    def _extract_type_hints(self, node: cst.FunctionDef) -> Dict[str, str]:
        """Extract type hints from function parameters and return type."""
        hints = {}

        # Parameter type hints
        for param in node.params.params:
            if param.annotation:
                hints[param.name.value] = str(param.annotation.annotation)

        # Return type hint
        if node.returns:
            hints["return"] = str(node.returns.annotation)

        return hints


class TreeSitterParser(BaseLanguageParser):
    """Generic Tree-sitter parser for multiple languages."""

    LANGUAGE_QUERIES = {
        "javascript": """
            (function_declaration name: (identifier) @name) @function
            (class_declaration name: (identifier) @name) @class
            (method_definition name: (property_identifier) @name) @method
        """,
        "typescript": """
            (function_declaration name: (identifier) @name) @function
            (class_declaration name: (identifier) @name) @class
            (method_definition name: (property_identifier) @name) @method
            (interface_declaration name: (type_identifier) @name) @interface
            (type_alias_declaration name: (type_identifier) @name) @type
        """,
        "go": """
            (function_declaration name: (identifier) @name) @function
            (method_declaration name: (field_identifier) @name) @method
            (type_declaration (type_spec name: (type_identifier) @name)) @type
        """,
        "rust": """
            (function_item name: (identifier) @name) @function
            (impl_item type: (type_identifier) @type) @impl
            (struct_item name: (type_identifier) @name) @struct
            (enum_item name: (type_identifier) @name) @enum
        """,
        "java": """
            (method_declaration name: (identifier) @name) @method
            (class_declaration name: (identifier) @name) @class
            (interface_declaration name: (identifier) @name) @interface
        """,
    }

    def __init__(self, language: str):
        """Initialize parser for specific language."""
        self.language = language
        self.parser = ts.Parser()
        # Note: In production, you would load language libraries here
        # For now, we'll use a simplified approach

    def parse_file(self, file_path: Path, content: str) -> List[CodeSymbol]:
        """Parse file using simplified pattern matching."""
        # Use regex-based extraction as fallback
        return self._extract_symbols_simple(content, file_path)

    def _extract_symbols_simple(self, content: str, file_path: Path) -> List[CodeSymbol]:
        """Extract symbols using regex patterns (simplified approach)."""
        import re

        symbols = []
        lines = content.split("\n")

        # Language-specific patterns
        patterns = {
            "javascript": [
                (r"^\s*function\s+(\w+)", "function"),
                (r"^\s*class\s+(\w+)", "class"),
                (r"^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*{", "method"),
            ],
            "typescript": [
                (r"^\s*function\s+(\w+)", "function"),
                (r"^\s*class\s+(\w+)", "class"),
                (r"^\s*interface\s+(\w+)", "interface"),
                (r"^\s*type\s+(\w+)", "type"),
                (r"^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*{", "method"),
            ],
            "go": [
                (r"^\s*func\s+(\w+)", "function"),
                (r"^\s*func\s+\([^)]+\)\s+(\w+)", "method"),
                (r"^\s*type\s+(\w+)\s+struct", "struct"),
                (r"^\s*type\s+(\w+)\s+interface", "interface"),
            ],
            "rust": [
                (r"^\s*fn\s+(\w+)", "function"),
                (r"^\s*struct\s+(\w+)", "struct"),
                (r"^\s*enum\s+(\w+)", "enum"),
                (r"^\s*impl\s+(?:\w+\s+for\s+)?(\w+)", "impl"),
            ],
            "java": [
                (r"^\s*(?:public|private|protected)?\s*class\s+(\w+)", "class"),
                (r"^\s*(?:public|private|protected)?\s*interface\s+(\w+)", "interface"),
                (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)?(\w+)\s*\([^)]*\)", "method"),
            ],
        }

        # Get patterns for this language
        lang_patterns = patterns.get(self.language, [])

        for line_no, line in enumerate(lines, 1):
            for pattern, kind in lang_patterns:
                match = re.match(pattern, line)
                if match:
                    symbols.append(
                        CodeSymbol(
                            name=match.group(1),
                            kind=kind,
                            signature=line.strip(),
                            docstring=None,
                            start_line=line_no,
                            end_line=line_no,
                            start_col=0,
                            end_col=len(line),
                            language=self.language,
                        )
                    )

        return symbols

    def _extract_comment(self, content: str, node) -> Optional[str]:
        """Extract comment/docstring near a node."""
        # Look for comment nodes before the current node
        prev = node.prev_sibling
        comments = []

        while prev and prev.type == "comment":
            comment_text = content[prev.start_byte : prev.end_byte]
            # Clean up comment markers
            if comment_text.startswith("//"):
                comment_text = comment_text[2:].strip()
            elif comment_text.startswith("/*"):
                comment_text = comment_text[2:-2].strip()
            comments.insert(0, comment_text)
            prev = prev.prev_sibling

        return "\n".join(comments) if comments else None


class CodeParser:
    """Unified code parser supporting multiple languages."""

    LANGUAGE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
    }

    def __init__(self):
        """Initialize the code parser."""
        self.parsers = {
            "python": PythonParser(),
        }

        # Initialize Tree-sitter parsers for other languages
        for lang in ["javascript", "typescript", "go", "rust", "java"]:
            self.parsers[lang] = TreeSitterParser(lang)

    def parse_file(self, file_path: Path) -> List[CodeSymbol]:
        """Parse a file and extract code symbols."""
        # Detect language from file extension
        language = self.LANGUAGE_EXTENSIONS.get(file_path.suffix.lower())
        if not language:
            logger.warning(f"Unsupported file extension: {file_path.suffix}")
            return []

        # Get appropriate parser
        parser = self.parsers.get(language)
        if not parser:
            logger.warning(f"No parser available for language: {language}")
            return []

        # Read file content
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try with different encoding
            import chardet

            with open(file_path, "rb") as f:
                raw_data = f.read()
                encoding = chardet.detect(raw_data)["encoding"]
                content = raw_data.decode(encoding or "utf-8", errors="ignore")

        # Parse the file
        return parser.parse_file(file_path, content)
