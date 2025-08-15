"""
Change analysis pipeline for parsing git diffs and extracting structured changes.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of changes detected in code."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class ChangeCategory(Enum):
    """Categories of code changes for documentation impact."""

    NEW_FEATURE = "new_feature"
    BREAKING_CHANGE = "breaking_change"
    CONFIG_CHANGE = "config_change"
    API_CHANGE = "api_change"
    MIGRATION = "migration"
    BUG_FIX = "bug_fix"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    TEST = "test"
    OTHER = "other"


@dataclass
class ChangedSymbol:
    """Represents a changed code symbol."""

    name: str
    kind: str  # function, class, method, variable, etc.
    change_type: ChangeType
    file_path: str
    start_line: int
    end_line: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    is_public: bool = True
    decorators: List[str] = field(default_factory=list)


@dataclass
class ChangedEndpoint:
    """Represents a changed API endpoint."""

    method: str  # GET, POST, PUT, DELETE, etc.
    path: str
    change_type: ChangeType
    file_path: str
    handler: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    response_schema: Optional[Dict[str, Any]] = None
    auth_required: bool = False


@dataclass
class ConfigChange:
    """Represents a configuration change."""

    key: str
    old_value: Optional[Any]
    new_value: Optional[Any]
    file_path: str
    change_type: ChangeType
    environment: Optional[str] = None  # dev, staging, prod


@dataclass
class MigrationChange:
    """Represents a database migration."""

    version: str
    description: str
    file_path: str
    change_type: ChangeType
    tables_affected: List[str] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)  # CREATE, ALTER, DROP, etc.


@dataclass
class StructuredChange:
    """Comprehensive change object with all extracted information."""

    file_path: str
    change_type: ChangeType
    category: ChangeCategory
    symbols: List[ChangedSymbol] = field(default_factory=list)
    endpoints: List[ChangedEndpoint] = field(default_factory=list)
    configs: List[ConfigChange] = field(default_factory=list)
    migrations: List[MigrationChange] = field(default_factory=list)
    breaking_changes: List[str] = field(default_factory=list)
    new_features: List[str] = field(default_factory=list)
    behavior_changes: List[str] = field(default_factory=list)
    diff_lines: List[str] = field(default_factory=list)
    impact_score: float = 0.0  # 0-1 score for documentation impact


class ChangeAnalyzer:
    """Analyzes git diffs to extract structured change information."""

    # Patterns for detecting different types of changes
    FUNCTION_PATTERN = re.compile(r"^\+?\s*(async\s+)?def\s+(\w+)\s*\(([^)]*)\)")
    CLASS_PATTERN = re.compile(r"^\+?\s*class\s+(\w+)\s*(?:\(([^)]*)\))?:")
    ENDPOINT_PATTERN = re.compile(r'@(app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']')
    CONFIG_PATTERN = re.compile(r"^\+?\s*(\w+)\s*=\s*(.+)")
    MIGRATION_PATTERN = re.compile(r'(create|alter|drop)_(table|column|index)\s*\(\s*["\'](\w+)["\']')
    BREAKING_INDICATORS = [
        "BREAKING",
        "breaking change",
        "incompatible",
        "removed",
        "deleted",
        "deprecated",
        "changed signature",
    ]

    def __init__(self):
        """Initialize the change analyzer."""
        self.diff_parser = DiffParser()

    def analyze_diff(self, diff: str) -> List[StructuredChange]:
        """
        Analyze a git diff and extract structured changes.

        Args:
            diff: Git diff output

        Returns:
            List of structured change objects
        """
        changes = []

        # Parse diff into file changes
        file_diffs = self.diff_parser.parse_diff(diff)

        for file_diff in file_diffs:
            # Create base structured change
            change = StructuredChange(
                file_path=file_diff["file_path"],
                change_type=self._determine_change_type(file_diff),
                category=ChangeCategory.OTHER,
                diff_lines=file_diff.get("lines", []),
            )

            # Extract different types of changes
            self._extract_symbols(file_diff, change)
            self._extract_endpoints(file_diff, change)
            self._extract_configs(file_diff, change)
            self._extract_migrations(file_diff, change)

            # Identify special change characteristics
            self._identify_breaking_changes(file_diff, change)
            self._identify_new_features(file_diff, change)
            self._identify_behavior_changes(file_diff, change)

            # Categorize and score the change
            change.category = self._categorize_change(change)
            change.impact_score = self._calculate_impact_score(change)

            changes.append(change)

        return changes

    def _determine_change_type(self, file_diff: Dict[str, Any]) -> ChangeType:
        """Determine the type of change from diff metadata."""
        if file_diff.get("is_new"):
            return ChangeType.ADDED
        elif file_diff.get("is_deleted"):
            return ChangeType.DELETED
        elif file_diff.get("is_renamed"):
            return ChangeType.RENAMED
        else:
            return ChangeType.MODIFIED

    def _extract_symbols(self, file_diff: Dict[str, Any], change: StructuredChange):
        """Extract changed symbols (functions, classes, etc.)."""
        file_path = file_diff["file_path"]

        # Skip non-code files
        if not self._is_code_file(file_path):
            return

        added_lines = file_diff.get("added_lines", [])
        removed_lines = file_diff.get("removed_lines", [])

        # Extract functions
        for line_num, line in added_lines:
            match = self.FUNCTION_PATTERN.match(line)
            if match:
                is_async, name, params = match.groups()
                symbol = ChangedSymbol(
                    name=name,
                    kind="async_function" if is_async else "function",
                    change_type=ChangeType.ADDED,
                    file_path=file_path,
                    start_line=line_num,
                    end_line=line_num,  # Will be updated with proper parsing
                    signature=f"{'async ' if is_async else ''}def {name}({params})",
                    is_public=not name.startswith("_"),
                )
                change.symbols.append(symbol)

        # Extract classes
        for line_num, line in added_lines:
            match = self.CLASS_PATTERN.match(line)
            if match:
                name, bases = match.groups()
                symbol = ChangedSymbol(
                    name=name,
                    kind="class",
                    change_type=ChangeType.ADDED,
                    file_path=file_path,
                    start_line=line_num,
                    end_line=line_num,
                    signature=f"class {name}({bases if bases else ''})",
                    is_public=not name.startswith("_"),
                )
                change.symbols.append(symbol)

        # Check for removed symbols
        for line_num, line in removed_lines:
            if self.FUNCTION_PATTERN.match(line) or self.CLASS_PATTERN.match(line):
                # Mark as potentially breaking change
                change.breaking_changes.append(f"Removed symbol at line {line_num}")

    def _extract_endpoints(self, file_diff: Dict[str, Any], change: StructuredChange):
        """Extract API endpoint changes."""
        file_path = file_diff["file_path"]

        # Only check Python files that might contain endpoints
        if not file_path.endswith(".py"):
            return

        added_lines = file_diff.get("added_lines", [])

        for i, (line_num, line) in enumerate(added_lines):
            match = self.ENDPOINT_PATTERN.search(line)
            if match:
                _, method, path = match.groups()

                # Look for handler function on next lines
                handler = None
                if i + 1 < len(added_lines):
                    next_line = added_lines[i + 1][1]
                    func_match = self.FUNCTION_PATTERN.match(next_line)
                    if func_match:
                        handler = func_match.group(2)

                endpoint = ChangedEndpoint(
                    method=method.upper(), path=path, change_type=ChangeType.ADDED, file_path=file_path, handler=handler
                )
                change.endpoints.append(endpoint)

    def _extract_configs(self, file_diff: Dict[str, Any], change: StructuredChange):
        """Extract configuration changes."""
        file_path = file_diff["file_path"]

        # Check for config files
        config_extensions = [".env", ".ini", ".cfg", ".yaml", ".yml", ".json", ".toml"]
        is_config_file = any(file_path.endswith(ext) for ext in config_extensions)
        is_settings_file = "settings" in file_path.lower() or "config" in file_path.lower()

        if not (is_config_file or is_settings_file):
            return

        added_lines = file_diff.get("added_lines", [])
        removed_lines = file_diff.get("removed_lines", [])

        # Track config changes
        removed_configs = {}
        for line_num, line in removed_lines:
            match = self.CONFIG_PATTERN.match(line)
            if match:
                key, value = match.groups()
                removed_configs[key] = value

        for line_num, line in added_lines:
            match = self.CONFIG_PATTERN.match(line)
            if match:
                key, value = match.groups()
                old_value = removed_configs.get(key)

                config = ConfigChange(
                    key=key,
                    old_value=old_value,
                    new_value=value,
                    file_path=file_path,
                    change_type=ChangeType.MODIFIED if old_value else ChangeType.ADDED,
                )
                change.configs.append(config)

    def _extract_migrations(self, file_diff: Dict[str, Any], change: StructuredChange):
        """Extract database migration changes."""
        file_path = file_diff["file_path"]

        # Check for migration files
        if "migration" not in file_path.lower() and "alembic" not in file_path.lower():
            return

        added_lines = file_diff.get("added_lines", [])

        # Extract migration version from filename
        version_match = re.search(r"(\d+)_(\w+)", Path(file_path).name)
        version = version_match.group(1) if version_match else "unknown"
        description = version_match.group(2) if version_match else "migration"

        tables = set()
        operations = set()

        for line_num, line in added_lines:
            match = self.MIGRATION_PATTERN.search(line.lower())
            if match:
                operation, target, table = match.groups()
                operations.add(f"{operation}_{target}")
                tables.add(table)

        if tables or operations:
            migration = MigrationChange(
                version=version,
                description=description,
                file_path=file_path,
                change_type=ChangeType.ADDED,
                tables_affected=list(tables),
                operations=list(operations),
            )
            change.migrations.append(migration)

    def _identify_breaking_changes(self, file_diff: Dict[str, Any], change: StructuredChange):
        """Identify breaking changes from diff content."""
        all_lines = file_diff.get("lines", [])

        for line in all_lines:
            line_lower = line.lower()
            if any(indicator in line_lower for indicator in self.BREAKING_INDICATORS):
                change.breaking_changes.append(line.strip())

        # Check for removed public APIs
        removed_lines = file_diff.get("removed_lines", [])
        for line_num, line in removed_lines:
            if self.FUNCTION_PATTERN.match(line):
                match = self.FUNCTION_PATTERN.match(line)
                if match and not match.group(2).startswith("_"):
                    change.breaking_changes.append(f"Removed public function: {match.group(2)}")

    def _identify_new_features(self, file_diff: Dict[str, Any], change: StructuredChange):
        """Identify new features from added code."""
        # New endpoints are features
        if change.endpoints:
            for endpoint in change.endpoints:
                change.new_features.append(f"New {endpoint.method} endpoint: {endpoint.path}")

        # New public functions/classes are features
        for symbol in change.symbols:
            if symbol.change_type == ChangeType.ADDED and symbol.is_public:
                change.new_features.append(f"New {symbol.kind}: {symbol.name}")

    def _identify_behavior_changes(self, file_diff: Dict[str, Any], change: StructuredChange):
        """Identify behavior changes from modified code."""
        # Look for modified functions
        modified_funcs = set()

        removed_lines = {line for _, line in file_diff.get("removed_lines", [])}
        added_lines = {line for _, line in file_diff.get("added_lines", [])}

        for line in removed_lines:
            match = self.FUNCTION_PATTERN.match(line)
            if match:
                func_name = match.group(2)
                # Check if same function exists in added lines
                for added_line in added_lines:
                    if func_name in added_line and self.FUNCTION_PATTERN.match(added_line):
                        modified_funcs.add(func_name)

        for func_name in modified_funcs:
            change.behavior_changes.append(f"Modified function: {func_name}")

    def _categorize_change(self, change: StructuredChange) -> ChangeCategory:
        """Categorize the change based on its content."""
        # Priority order for categorization
        if change.breaking_changes:
            return ChangeCategory.BREAKING_CHANGE
        elif change.migrations:
            return ChangeCategory.MIGRATION
        elif change.endpoints:
            return ChangeCategory.API_CHANGE
        elif change.configs:
            return ChangeCategory.CONFIG_CHANGE
        elif change.new_features:
            return ChangeCategory.NEW_FEATURE
        elif "test" in change.file_path.lower():
            return ChangeCategory.TEST
        elif change.file_path.endswith(".md"):
            return ChangeCategory.DOCUMENTATION
        elif change.behavior_changes:
            return ChangeCategory.REFACTOR
        elif "fix" in " ".join(change.diff_lines).lower():
            return ChangeCategory.BUG_FIX
        else:
            return ChangeCategory.OTHER

    def _calculate_impact_score(self, change: StructuredChange) -> float:
        """
        Calculate documentation impact score (0-1).
        Higher scores indicate greater need for documentation updates.
        """
        score = 0.0

        # Breaking changes have highest impact
        if change.breaking_changes:
            score = max(score, 0.9)

        # API changes are high impact
        if change.endpoints:
            score = max(score, 0.8)

        # New features need documentation
        if change.new_features:
            score = max(score, 0.7)

        # Config changes need documentation
        if change.configs:
            score = max(score, 0.6)

        # Migrations might need documentation
        if change.migrations:
            score = max(score, 0.5)

        # Public symbol changes
        public_symbols = [s for s in change.symbols if s.is_public]
        if public_symbols:
            score = max(score, 0.4 + min(len(public_symbols) * 0.1, 0.4))

        # Behavior changes might need notes
        if change.behavior_changes:
            score = max(score, 0.3)

        return min(score, 1.0)

    def _is_code_file(self, file_path: str) -> bool:
        """Check if file is a code file."""
        code_extensions = [
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".cs",
            ".rb",
        ]
        return any(file_path.endswith(ext) for ext in code_extensions)


class DiffParser:
    """Parses git diff output into structured format."""

    def parse_diff(self, diff: str) -> List[Dict[str, Any]]:
        """
        Parse a git diff into structured file changes.

        Args:
            diff: Raw git diff output

        Returns:
            List of file diff dictionaries
        """
        file_diffs = []
        current_file = None
        current_hunk = None

        lines = diff.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # New file diff
            if line.startswith("diff --git"):
                if current_file:
                    file_diffs.append(current_file)

                # Extract file paths
                match = re.match(r"diff --git a/(.*) b/(.*)", line)
                if match:
                    old_path, new_path = match.groups()
                    current_file = {
                        "file_path": new_path,
                        "old_path": old_path,
                        "lines": [],
                        "added_lines": [],
                        "removed_lines": [],
                        "hunks": [],
                    }

            # File metadata
            elif line.startswith("new file mode"):
                if current_file:
                    current_file["is_new"] = True
            elif line.startswith("deleted file mode"):
                if current_file:
                    current_file["is_deleted"] = True
            elif line.startswith("rename from"):
                if current_file:
                    current_file["is_renamed"] = True

            # Hunk header
            elif line.startswith("@@"):
                match = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", line)
                if match and current_file:
                    old_start, old_count, new_start, new_count = match.groups()
                    current_hunk = {
                        "old_start": int(old_start),
                        "old_count": int(old_count) if old_count else 1,
                        "new_start": int(new_start),
                        "new_count": int(new_count) if new_count else 1,
                        "lines": [],
                    }
                    current_file["hunks"].append(current_hunk)

            # Diff lines
            elif current_file:
                current_file["lines"].append(line)

                if line.startswith("+") and not line.startswith("+++"):
                    line_num = self._calculate_line_number(current_file, i)
                    current_file["added_lines"].append((line_num, line[1:]))
                elif line.startswith("-") and not line.startswith("---"):
                    line_num = self._calculate_line_number(current_file, i)
                    current_file["removed_lines"].append((line_num, line[1:]))

                if current_hunk:
                    current_hunk["lines"].append(line)

            i += 1

        # Add last file
        if current_file:
            file_diffs.append(current_file)

        return file_diffs

    def _calculate_line_number(self, file_diff: Dict[str, Any], current_index: int) -> int:
        """Calculate the line number for a diff line."""
        # Simplified line number calculation
        # In a real implementation, this would track position within hunks
        if file_diff.get("hunks"):
            last_hunk = file_diff["hunks"][-1]
            return last_hunk["new_start"] + len(last_hunk["lines"])
        return current_index
