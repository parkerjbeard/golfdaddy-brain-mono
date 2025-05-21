import os
import sys
import pytest
import asyncio

# Ensure the repository root is on the path so we can import doc_agent
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.insert(0, ROOT_DIR)

from doc_agent.client import _retry, _async_retry
from tests.unit.utils import test_helpers
from app.config import settings as settings_module

# The shared tests expect this attribute on settings
if not hasattr(settings_module.settings, "SUPABASE_SERVICE_ROLE_KEY"):
    object.__setattr__(settings_module.settings, "SUPABASE_SERVICE_ROLE_KEY", "dummy")

# Tests for _retry utility function
def test_retry_success_after_failures():
    call_count = {"count": 0}

    def flaky():
        call_count["count"] += 1
        if call_count["count"] < 3:
            raise ValueError("fail")
        return "ok"

    result = _retry(flaky, retries=3)
    assert result == "ok"
    assert call_count["count"] == 3


def test_retry_raises_after_exhausted():
    def always_fail():
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        _retry(always_fail, retries=2)


# Tests for _async_retry utility function
def test_async_retry_success_after_failures():
    call_count = {"count": 0}

    async def flaky_async():
        call_count["count"] += 1
        if call_count["count"] < 2:
            raise ValueError("fail")
        return "ok"

    result = asyncio.run(_async_retry(flaky_async, retries=2))
    assert result == "ok"
    assert call_count["count"] == 2


def test_async_retry_raises_after_exhausted():
    async def always_fail_async():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        asyncio.run(_async_retry(always_fail_async, retries=1))


# Tests for test helper utilities

def test_load_test_data(tmp_path, monkeypatch):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    sample_file = fixtures_dir / "sample.json"
    sample_file.write_text('{"foo": 1}')

    base_tests_dir = os.path.dirname(os.path.dirname(test_helpers.__file__))

    original_join = os.path.join

    def join_override(dir1, dir2, *args):
        if dir1 == base_tests_dir and dir2 == "fixtures":
            return str(fixtures_dir)
        return original_join(dir1, dir2, *args)

    monkeypatch.setattr(os.path, "join", join_override)
    data = test_helpers.load_test_data("sample.json")
    assert data == {"foo": 1}


def test_assert_dict_contains_subset():
    subset = {"a": 1, "b": 2}
    full = {"a": 1, "b": 2, "c": 3}
    test_helpers.assert_dict_contains_subset(subset, full)

    with pytest.raises(AssertionError):
        test_helpers.assert_dict_contains_subset({"x": 5}, full)


def test_get_test_file_path():
    path = test_helpers.get_test_file_path("fixtures/sample_data.json")
    assert os.path.isabs(path)
    assert path.endswith(os.path.join("fixtures", "sample_data.json"))
