"""
Unit tests for the change analyzer service.
"""

from app.services.change_analyzer import (
    ChangeAnalyzer,
    ChangeCategory,
    ChangeType,
    DiffParser,
)


class TestDiffParser:
    """Test the diff parser."""

    def test_parse_simple_diff(self):
        """Test parsing a simple diff."""
        diff = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,4 +1,5 @@
 def hello():
     print("Hello")
+    print("World")
 
 def goodbye():"""

        parser = DiffParser()
        file_diffs = parser.parse_diff(diff)

        assert len(file_diffs) == 1
        assert file_diffs[0]["file_path"] == "test.py"
        assert len(file_diffs[0]["added_lines"]) == 1
        assert file_diffs[0]["added_lines"][0][1] == '    print("World")'

    def test_parse_new_file(self):
        """Test parsing a new file diff."""
        diff = """diff --git a/new.py b/new.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/new.py
@@ -0,0 +1,3 @@
+def new_function():
+    return "new"
+"""

        parser = DiffParser()
        file_diffs = parser.parse_diff(diff)

        assert len(file_diffs) == 1
        assert file_diffs[0]["file_path"] == "new.py"
        assert file_diffs[0].get("is_new") is True
        assert len(file_diffs[0]["added_lines"]) >= 2  # May include empty line

    def test_parse_deleted_file(self):
        """Test parsing a deleted file diff."""
        diff = """diff --git a/old.py b/old.py
deleted file mode 100644
index 1234567..0000000
--- a/old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-def old_function():
-    return "old"
-"""

        parser = DiffParser()
        file_diffs = parser.parse_diff(diff)

        assert len(file_diffs) == 1
        assert file_diffs[0]["file_path"] == "old.py"
        assert file_diffs[0].get("is_deleted") is True
        assert len(file_diffs[0]["removed_lines"]) >= 2  # May include empty line

    def test_parse_multiple_files(self):
        """Test parsing a diff with multiple files."""
        diff = """diff --git a/file1.py b/file1.py
index 1234567..abcdefg 100644
--- a/file1.py
+++ b/file1.py
@@ -1,2 +1,3 @@
 def func1():
+    # New comment
     pass
diff --git a/file2.py b/file2.py
index 2345678..bcdefgh 100644
--- a/file2.py
+++ b/file2.py
@@ -1,2 +1,2 @@
-def func2():
+def func2_renamed():
     pass"""

        parser = DiffParser()
        file_diffs = parser.parse_diff(diff)

        assert len(file_diffs) == 2
        assert file_diffs[0]["file_path"] == "file1.py"
        assert file_diffs[1]["file_path"] == "file2.py"


class TestChangeAnalyzer:
    """Test the change analyzer."""

    def test_extract_function_symbols(self):
        """Test extracting function symbols from diff."""
        diff = """diff --git a/api.py b/api.py
index 1234567..abcdefg 100644
--- a/api.py
+++ b/api.py
@@ -1,2 +1,6 @@
 import os
+
+def process_data(input_data: dict) -> dict:
+    \"\"\"Process input data.\"\"\"
+    return {"processed": input_data}
"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        assert len(changes) == 1
        change = changes[0]
        assert len(change.symbols) >= 1

        func_symbol = change.symbols[0]
        assert func_symbol.name == "process_data"
        assert func_symbol.kind == "function"
        assert func_symbol.change_type == ChangeType.ADDED
        assert func_symbol.is_public is True

    def test_extract_class_symbols(self):
        """Test extracting class symbols from diff."""
        diff = """diff --git a/models.py b/models.py
index 1234567..abcdefg 100644
--- a/models.py
+++ b/models.py
@@ -1,2 +1,8 @@
 from dataclasses import dataclass
+
+class UserManager:
+    \"\"\"Manages user operations.\"\"\"
+    
+    def create_user(self, name: str):
+        pass
"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        assert len(changes) == 1
        change = changes[0]
        assert any(s.name == "UserManager" and s.kind == "class" for s in change.symbols)

    def test_extract_endpoints(self):
        """Test extracting API endpoints from diff."""
        diff = """diff --git a/routes.py b/routes.py
index 1234567..abcdefg 100644
--- a/routes.py
+++ b/routes.py
@@ -1,2 +1,6 @@
 from fastapi import APIRouter
+
+@router.get("/users/{user_id}")
+async def get_user(user_id: int):
+    return {"user_id": user_id}
"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        assert len(changes) == 1
        change = changes[0]
        assert len(change.endpoints) >= 1

        endpoint = change.endpoints[0]
        assert endpoint.method == "GET"
        assert endpoint.path == "/users/{user_id}"
        assert endpoint.handler == "get_user"

    def test_extract_config_changes(self):
        """Test extracting configuration changes."""
        diff = """diff --git a/settings.py b/settings.py
index 1234567..abcdefg 100644
--- a/settings.py
+++ b/settings.py
@@ -1,3 +1,3 @@
-DEBUG = True
+DEBUG = False
 
+MAX_CONNECTIONS = 100
"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        assert len(changes) == 1
        change = changes[0]
        assert len(change.configs) >= 2

        # Check DEBUG change
        debug_config = next((c for c in change.configs if c.key == "DEBUG"), None)
        assert debug_config is not None
        assert debug_config.old_value == "True"
        assert debug_config.new_value == "False"

        # Check new config
        max_conn = next((c for c in change.configs if c.key == "MAX_CONNECTIONS"), None)
        assert max_conn is not None
        assert max_conn.new_value == "100"

    def test_identify_breaking_changes(self):
        """Test identifying breaking changes."""
        diff = """diff --git a/api.py b/api.py
index 1234567..abcdefg 100644
--- a/api.py
+++ b/api.py
@@ -1,4 +1,4 @@
-def process_data(data):
-    # BREAKING CHANGE: Changed signature
-    return data
+def process_data(data, format='json'):
+    # Breaking change: Added required parameter
+    return format_data(data, format)
"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        assert len(changes) == 1
        change = changes[0]
        assert len(change.breaking_changes) > 0
        assert change.category == ChangeCategory.BREAKING_CHANGE

    def test_identify_new_features(self):
        """Test identifying new features."""
        diff = """diff --git a/features.py b/features.py
index 1234567..abcdefg 100644
--- a/features.py
+++ b/features.py
@@ -1,2 +1,6 @@
 import json
+
+def export_to_csv(data):
+    \"\"\"New feature: Export data to CSV format.\"\"\"
+    pass
"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        assert len(changes) == 1
        change = changes[0]
        assert len(change.new_features) > 0
        assert "export_to_csv" in change.new_features[0]

    def test_categorize_changes(self):
        """Test change categorization."""
        # Test API change
        api_diff = """diff --git a/api.py b/api.py
index 1234567..abcdefg 100644
--- a/api.py
+++ b/api.py
@@ -1,2 +1,4 @@
+@app.post("/users")
+def create_user():
     pass
"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(api_diff)
        assert changes[0].category == ChangeCategory.API_CHANGE

        # Test config change
        config_diff = """diff --git a/.env b/.env
index 1234567..abcdefg 100644
--- a/.env
+++ b/.env
@@ -1 +1 @@
-PORT=3000
+PORT=8000
"""

        changes = analyzer.analyze_diff(config_diff)
        assert changes[0].category == ChangeCategory.CONFIG_CHANGE

    def test_calculate_impact_score(self):
        """Test impact score calculation."""
        # High impact - breaking change
        breaking_diff = """diff --git a/api.py b/api.py
index 1234567..abcdefg 100644
--- a/api.py
+++ b/api.py
@@ -1,3 +1,2 @@
-def old_function():
-    # BREAKING: Removed function
+# Function removed
"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(breaking_diff)
        assert changes[0].impact_score >= 0.9

        # Medium impact - new feature
        feature_diff = """diff --git a/features.py b/features.py
index 1234567..abcdefg 100644
--- a/features.py
+++ b/features.py
@@ -1 +1,3 @@
+def new_feature():
+    pass
"""

        changes = analyzer.analyze_diff(feature_diff)
        assert 0.4 <= changes[0].impact_score <= 0.8

        # Low impact - minor change
        minor_diff = """diff --git a/utils.py b/utils.py
index 1234567..abcdefg 100644
--- a/utils.py
+++ b/utils.py
@@ -1,2 +1,2 @@
 def _internal_helper():
-    return 1
+    return 2
"""

        changes = analyzer.analyze_diff(minor_diff)
        assert changes[0].impact_score < 0.5

    def test_extract_migrations(self):
        """Test extracting database migrations."""
        diff = """diff --git a/migrations/001_create_users.py b/migrations/001_create_users.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/migrations/001_create_users.py
@@ -0,0 +1,5 @@
+def upgrade():
+    create_table('users')
+    
+def downgrade():
+    drop_table('users')
"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        assert len(changes) == 1
        change = changes[0]
        assert len(change.migrations) > 0

        migration = change.migrations[0]
        assert migration.version == "001"
        assert "users" in migration.tables_affected
        assert "create_table" in migration.operations

    def test_private_vs_public_symbols(self):
        """Test distinguishing between private and public symbols."""
        diff = """diff --git a/module.py b/module.py
index 1234567..abcdefg 100644
--- a/module.py
+++ b/module.py
@@ -1 +1,7 @@
+def public_function():
+    pass
+
+def _private_function():
+    pass
+
 pass
"""

        analyzer = ChangeAnalyzer()
        changes = analyzer.analyze_diff(diff)

        public_symbols = [s for s in changes[0].symbols if s.is_public]
        private_symbols = [s for s in changes[0].symbols if not s.is_public]

        assert len(public_symbols) >= 1
        assert len(private_symbols) >= 1
        assert public_symbols[0].name == "public_function"
        assert private_symbols[0].name == "_private_function"
