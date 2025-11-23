"""Unit tests for cache flow logic."""

from unittest.mock import Mock, AsyncMock
import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from pydantic import BaseModel

from app.api.v1.shared.cache_flow import handle_cache_errors, handle_cache_lookup
from app.services.cache import CacheService
from app.services.mvg_errors import MVGServiceError, StationNotFoundError


class TestHandleCacheLookup:
    """Tests for handle_cache_lookup."""

    @pytest.fixture
    def mock_deps(self):
        cache = Mock(spec=CacheService)
        cache.get_json = AsyncMock()
        cache.get_stale_json = AsyncMock()

        response = Mock(spec=Response)
        response.headers = {}

        return {
            "cache": cache,
            "response": response,
            "background_tasks": Mock(spec=BackgroundTasks),
            "refresh_func": Mock(),
            "model_class": Mock(),
        }

    @pytest.mark.asyncio
    async def test_hit_returns_result(self, mock_deps):
        mock_deps["cache"].get_json.return_value = {"data": "fresh"}

        class Model(BaseModel):
            data: str

        result = await handle_cache_lookup(
            cache=mock_deps["cache"],
            cache_key="key",
            cache_name="test",
            response=mock_deps["response"],
            background_tasks=mock_deps["background_tasks"],
            refresh_func=mock_deps["refresh_func"],
            refresh_kwargs={},
            model_class=Model,
        )
        assert result.status == "hit"
        assert result.data.data == "fresh"

    @pytest.mark.asyncio
    async def test_miss_returns_none_data(self, mock_deps):
        mock_deps["cache"].get_json.return_value = None
        mock_deps["cache"].get_stale_json.return_value = None

        class Model(BaseModel):
            data: str

        result = await handle_cache_lookup(
            cache=mock_deps["cache"],
            cache_key="key",
            cache_name="test",
            response=mock_deps["response"],
            background_tasks=mock_deps["background_tasks"],
            refresh_func=mock_deps["refresh_func"],
            refresh_kwargs={},
            model_class=Model,
        )
        assert result.status == "miss"
        assert result.data is None

    @pytest.mark.asyncio
    async def test_stale_returns_stale_data(self, mock_deps):
        mock_deps["cache"].get_json.return_value = None
        mock_deps["cache"].get_stale_json.return_value = {"data": "stale"}

        class Model(BaseModel):
            data: str

        result = await handle_cache_lookup(
            cache=mock_deps["cache"],
            cache_key="key",
            cache_name="test",
            response=mock_deps["response"],
            background_tasks=mock_deps["background_tasks"],
            refresh_func=mock_deps["refresh_func"],
            refresh_kwargs={},
            model_class=Model,
        )
        assert result.status == "stale-refresh"
        assert result.data.data == "stale"
        mock_deps["background_tasks"].add_task.assert_called_once()

    """Tests for handle_cache_errors."""

    @pytest.mark.asyncio
    async def test_station_not_found_raises_404_async(self):
        cache = Mock(spec=CacheService)

        class Model(BaseModel):
            data: str

        with pytest.raises(HTTPException) as exc:
            await handle_cache_errors(
                cache=cache,
                cache_key="key",
                cache_name="test",
                exc=StationNotFoundError("Station not found"),
                model_class=Model,
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_mvg_service_error_raises_502(self):
        cache = Mock(spec=CacheService)

        class Model(BaseModel):
            data: str

        with pytest.raises(HTTPException) as exc:
            await handle_cache_errors(
                cache=cache,
                cache_key="key",
                cache_name="test",
                exc=MVGServiceError("Service error"),
                model_class=Model,
                allow_stale_fallback=False,
            )
        assert exc.value.status_code == 502

    @pytest.mark.asyncio
    async def test_timeout_with_stale_fallback(self):
        cache = Mock(spec=CacheService)
        cache.get_stale_json.return_value = {"data": "stale"}

        class Model(BaseModel):
            data: str

        result = await handle_cache_errors(
            cache=cache,
            cache_key="key",
            cache_name="test",
            exc=TimeoutError(),
            model_class=Model,
            allow_stale_fallback=True,
        )
        assert result.status == "stale"
        assert result.data.data == "stale"

    @pytest.mark.asyncio
    async def test_timeout_without_stale_fallback_raises_503(self):
        cache = Mock(spec=CacheService)
        cache.get_stale_json.return_value = None

        class Model(BaseModel):
            data: str

        with pytest.raises(HTTPException) as exc:
            await handle_cache_errors(
                cache=cache,
                cache_key="key",
                cache_name="test",
                exc=TimeoutError(),
                model_class=Model,
                allow_stale_fallback=True,
            )
        assert exc.value.status_code == 503
