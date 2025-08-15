"""
Unit tests for code parser service.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.services.code_parser import CodeParser, CodeSymbol, PythonParser, TreeSitterParser


class TestCodeSymbol:
    """Test CodeSymbol dataclass."""

    def test_symbol_creation(self):
        """Test creating a CodeSymbol."""
        symbol = CodeSymbol(
            name="test_function",
            kind="function",
            signature="def test_function(x: int) -> str",
            docstring="Test function docstring",
            start_line=10,
            end_line=15,
            start_col=0,
            end_col=0,
            decorators=["@pytest.mark.asyncio"],
            type_hints={"x": "int", "return": "str"},
            language="python",
        )

        assert symbol.name == "test_function"
        assert symbol.kind == "function"
        assert symbol.language == "python"
        assert len(symbol.decorators) == 1
        assert symbol.type_hints["return"] == "str"


class TestPythonParser:
    """Test Python-specific parser."""

    def test_parse_function(self):
        """Test parsing a Python function."""
        parser = PythonParser()

        code = '''
def hello_world(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"
'''

        symbols = parser.parse_file(Path("test.py"), code)

        assert len(symbols) == 1
        symbol = symbols[0]
        assert symbol.name == "hello_world"
        assert symbol.kind == "function"
        assert "Say hello to someone." in symbol.docstring
        assert symbol.language == "python"

    def test_parse_class(self):
        """Test parsing a Python class."""
        parser = PythonParser()

        code = '''
class TestClass:
    """Test class docstring."""
    
    def __init__(self, value: int):
        """Initialize the class."""
        self.value = value
    
    def get_value(self) -> int:
        """Get the value."""
        return self.value
'''

        symbols = parser.parse_file(Path("test.py"), code)

        # Should find class and methods
        assert len(symbols) >= 3

        # Check class
        class_symbol = next(s for s in symbols if s.name == "TestClass")
        assert class_symbol.kind == "class"
        assert "Test class docstring" in class_symbol.docstring

        # Check methods
        init_symbol = next(s for s in symbols if s.name == "__init__")
        assert init_symbol.kind == "method"

        get_value_symbol = next(s for s in symbols if s.name == "get_value")
        assert get_value_symbol.kind == "method"

    def test_parse_decorated_function(self):
        """Test parsing a decorated function."""
        parser = PythonParser()

        code = '''
@pytest.mark.asyncio
@cache
async def async_function():
    """Async function."""
    await asyncio.sleep(1)
'''

        symbols = parser.parse_file(Path("test.py"), code)

        assert len(symbols) == 1
        symbol = symbols[0]
        assert symbol.name == "async_function"
        assert len(symbol.decorators) >= 1  # Should have decorators

    def test_parse_with_type_hints(self):
        """Test parsing functions with type hints."""
        parser = PythonParser()

        code = '''
from typing import List, Optional

def process_items(items: List[str], max_count: Optional[int] = None) -> List[str]:
    """Process a list of items."""
    if max_count:
        return items[:max_count]
    return items
'''

        symbols = parser.parse_file(Path("test.py"), code)

        assert len(symbols) == 1
        symbol = symbols[0]
        assert symbol.name == "process_items"
        assert symbol.type_hints is not None
        # Type hints should be extracted
        assert "items" in symbol.type_hints or "return" in symbol.type_hints

    def test_parse_invalid_python(self):
        """Test parsing invalid Python code."""
        parser = PythonParser()

        code = """
def broken_function(
    This is not valid Python
"""

        symbols = parser.parse_file(Path("test.py"), code)

        # Should handle error gracefully and return empty list
        assert symbols == []


class TestTreeSitterParser:
    """Test Tree-sitter based parser."""

    def test_parse_javascript(self):
        """Test parsing JavaScript code with simplified parser."""
        parser = TreeSitterParser("javascript")

        code = """
function greet(name) {
    return `Hello, ${name}!`;
}

class Person {
    constructor(name) {
        this.name = name;
    }
    
    getName() {
        return this.name;
    }
}
"""

        symbols = parser.parse_file(Path("test.js"), code)

        # Verify we got some symbols (simplified parser should find function and class)
        assert len(symbols) >= 2

        # Check that we found the function
        func_symbol = next((s for s in symbols if s.name == "greet"), None)
        assert func_symbol is not None
        assert func_symbol.kind == "function"

    def test_unsupported_language(self):
        """Test parsing with unsupported language."""
        parser = TreeSitterParser("unknown_language")

        symbols = parser.parse_file(Path("test.unknown"), "code")

        # Should return empty list for unsupported language (no patterns defined)
        assert symbols == []


class TestCodeParser:
    """Test unified code parser."""

    def test_detect_language_from_extension(self):
        """Test language detection from file extension."""
        parser = CodeParser()

        assert parser.LANGUAGE_EXTENSIONS[".py"] == "python"
        assert parser.LANGUAGE_EXTENSIONS[".js"] == "javascript"
        assert parser.LANGUAGE_EXTENSIONS[".ts"] == "typescript"
        assert parser.LANGUAGE_EXTENSIONS[".go"] == "go"
        assert parser.LANGUAGE_EXTENSIONS[".rs"] == "rust"
        assert parser.LANGUAGE_EXTENSIONS[".java"] == "java"

    def test_parse_python_file(self):
        """Test parsing a Python file."""
        parser = CodeParser()

        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                '''
def test_function():
    """Test function."""
    return "test"
'''
            )
            temp_path = Path(f.name)

        try:
            symbols = parser.parse_file(temp_path)

            assert len(symbols) == 1
            assert symbols[0].name == "test_function"
            assert symbols[0].kind == "function"
            assert symbols[0].language == "python"
        finally:
            temp_path.unlink()

    def test_parse_unsupported_file(self):
        """Test parsing a file with unsupported extension."""
        parser = CodeParser()

        # Create a temporary file with unsupported extension
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            f.write("Some content")
            temp_path = Path(f.name)

        try:
            symbols = parser.parse_file(temp_path)

            # Should return empty list for unsupported files
            assert symbols == []
        finally:
            temp_path.unlink()

    def test_parse_file_with_encoding_issue(self):
        """Test parsing a file with encoding issues."""
        parser = CodeParser()

        # Create a temporary file with non-UTF8 encoding
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".py", delete=False) as f:
            # Write bytes that might cause encoding issues
            f.write(b'def test():\n    return "\xe9"')
            temp_path = Path(f.name)

        try:
            # Should handle encoding gracefully using chardet
            symbols = parser.parse_file(temp_path)

            # Should still parse if possible
            assert isinstance(symbols, list)
            # Should find the test function
            if symbols:
                assert symbols[0].name == "test"
        finally:
            temp_path.unlink()
