from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from postgrest.exceptions import APIError

from app.core.exceptions import DatabaseError
from app.repositories.pull_request_repository import PullRequestRepository


def _build_mock_client():
    """Return a minimal Supabase client mock with chained query builders."""
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.in_.return_value = query
    query.gte.return_value = query
    query.lte.return_value = query
    query.order.return_value = query
    query.execute = MagicMock()

    client = MagicMock()
    client.table.return_value = query
    return client


def _missing_table_error():
    return APIError(
        {
            "message": 'relation "public.pull_requests" does not exist',
            "code": "42P01",
            "hint": None,
            "details": None,
        }
    )


@pytest.mark.asyncio
async def test_get_pull_requests_for_users_missing_table_returns_empty_map():
    repo = PullRequestRepository(client=_build_mock_client())
    user_id = uuid4()

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.side_effect = _missing_table_error()
        result = await repo.get_pull_requests_for_users_in_range([user_id], date(2025, 11, 9), date(2025, 11, 22))

    assert result == {user_id: []}


@pytest.mark.asyncio
async def test_get_pull_requests_by_user_missing_table_returns_empty_list():
    repo = PullRequestRepository(client=_build_mock_client())
    user_id = uuid4()

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.side_effect = _missing_table_error()
        result = await repo.get_pull_requests_by_user_in_range(user_id, date(2025, 11, 9), date(2025, 11, 22))

    assert result == []


@pytest.mark.asyncio
async def test_api_error_other_codes_raise_database_error():
    repo = PullRequestRepository(client=_build_mock_client())
    user_id = uuid4()

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        mock_to_thread.side_effect = APIError({"message": "boom", "code": "999"})
        with pytest.raises(DatabaseError):
            await repo.get_pull_requests_by_user_in_range(user_id, date(2025, 11, 9), date(2025, 11, 22))
