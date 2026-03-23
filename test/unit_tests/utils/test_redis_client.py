# Copyright 2022-2023 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from unittest.mock import MagicMock, patch

from orchestrator.utils.redis_client import (
    REDIS_RETRY_ON_ERROR,
    REDIS_RETRY_ON_TIMEOUT,
    create_redis_asyncio_client,
    create_redis_client,
)

REDIS_URL = "redis://localhost:6379/0"


class TestCreateRedisClient:
    def test_calls_from_url_with_correct_url(self) -> None:
        with patch("orchestrator.utils.redis_client.Redis") as mock_redis:
            create_redis_client(REDIS_URL)
            mock_redis.from_url.assert_called_once()
            call_args = mock_redis.from_url.call_args
            assert call_args[0][0] == REDIS_URL

    def test_passes_retry_on_error(self) -> None:
        with patch("orchestrator.utils.redis_client.Redis") as mock_redis:
            create_redis_client(REDIS_URL)
            kwargs = mock_redis.from_url.call_args[1]
            assert kwargs["retry_on_error"] == REDIS_RETRY_ON_ERROR

    def test_passes_retry_on_timeout(self) -> None:
        with patch("orchestrator.utils.redis_client.Redis") as mock_redis:
            create_redis_client(REDIS_URL)
            kwargs = mock_redis.from_url.call_args[1]
            assert kwargs["retry_on_timeout"] == REDIS_RETRY_ON_TIMEOUT

    def test_passes_retry_object(self) -> None:
        with patch("orchestrator.utils.redis_client.Redis") as mock_redis:
            with patch("orchestrator.utils.redis_client.Retry") as mock_retry:
                create_redis_client(REDIS_URL)
                kwargs = mock_redis.from_url.call_args[1]
                assert kwargs["retry"] is mock_retry.return_value

    def test_returns_result_from_from_url(self) -> None:
        mock_client = MagicMock()
        with patch("orchestrator.utils.redis_client.Redis") as mock_redis:
            mock_redis.from_url.return_value = mock_client
            result = create_redis_client(REDIS_URL)
        assert result is mock_client

    def test_accepts_pydantic_redis_dsn(self) -> None:
        from pydantic import RedisDsn

        dsn = RedisDsn("redis://localhost:6379/1")
        with patch("orchestrator.utils.redis_client.Redis") as mock_redis:
            create_redis_client(dsn)
            call_args = mock_redis.from_url.call_args
            # Must stringify the DSN
            assert isinstance(call_args[0][0], str)


class TestCreateRedisAsyncioClient:
    def test_calls_from_url_with_correct_url(self) -> None:
        with patch("orchestrator.utils.redis_client.AIORedis") as mock_redis:
            create_redis_asyncio_client(REDIS_URL)
            mock_redis.from_url.assert_called_once()
            call_args = mock_redis.from_url.call_args
            assert call_args[0][0] == REDIS_URL

    def test_passes_retry_on_error(self) -> None:
        with patch("orchestrator.utils.redis_client.AIORedis") as mock_redis:
            create_redis_asyncio_client(REDIS_URL)
            kwargs = mock_redis.from_url.call_args[1]
            assert kwargs["retry_on_error"] == REDIS_RETRY_ON_ERROR

    def test_passes_retry_on_timeout(self) -> None:
        with patch("orchestrator.utils.redis_client.AIORedis") as mock_redis:
            create_redis_asyncio_client(REDIS_URL)
            kwargs = mock_redis.from_url.call_args[1]
            assert kwargs["retry_on_timeout"] == REDIS_RETRY_ON_TIMEOUT

    def test_passes_retry_object(self) -> None:
        with patch("orchestrator.utils.redis_client.AIORedis") as mock_redis:
            with patch("orchestrator.utils.redis_client.AIORetry") as mock_retry:
                create_redis_asyncio_client(REDIS_URL)
                kwargs = mock_redis.from_url.call_args[1]
                assert kwargs["retry"] is mock_retry.return_value

    def test_returns_result_from_from_url(self) -> None:
        mock_client = MagicMock()
        with patch("orchestrator.utils.redis_client.AIORedis") as mock_redis:
            mock_redis.from_url.return_value = mock_client
            result = create_redis_asyncio_client(REDIS_URL)
        assert result is mock_client

    def test_accepts_pydantic_redis_dsn(self) -> None:
        from pydantic import RedisDsn

        dsn = RedisDsn("redis://localhost:6379/2")
        with patch("orchestrator.utils.redis_client.AIORedis") as mock_redis:
            create_redis_asyncio_client(dsn)
            call_args = mock_redis.from_url.call_args
            assert isinstance(call_args[0][0], str)


class TestRedisConstants:
    def test_retry_on_timeout_is_true(self) -> None:
        assert REDIS_RETRY_ON_TIMEOUT is True

    def test_retry_on_error_contains_connection_error(self) -> None:
        import redis.exceptions

        assert redis.exceptions.ConnectionError in REDIS_RETRY_ON_ERROR
