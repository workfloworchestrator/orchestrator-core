# Copyright 2019-2020 SURF, GÉANT.
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

import pytest

from orchestrator.settings import AppSettings, Authorizers, ExecutorType, LifecycleValidationMode, get_authorizers


class TestExecutorType:
    def test_values_exist(self) -> None:
        assert str(ExecutorType.WORKER) == "celery"
        assert str(ExecutorType.THREADPOOL) == "threadpool"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("celery", ExecutorType.WORKER),
            ("threadpool", ExecutorType.THREADPOOL),
        ],
        ids=["celery", "threadpool"],
    )
    def test_roundtrip_from_string(self, raw: str, expected: ExecutorType) -> None:
        assert ExecutorType(raw) is expected

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            ExecutorType("invalid")


class TestLifecycleValidationMode:
    def test_values_exist(self) -> None:
        assert str(LifecycleValidationMode.STRICT) == "strict"
        assert str(LifecycleValidationMode.LOOSE) == "loose"
        assert str(LifecycleValidationMode.IGNORED) == "ignored"

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("strict", LifecycleValidationMode.STRICT),
            ("loose", LifecycleValidationMode.LOOSE),
            ("ignored", LifecycleValidationMode.IGNORED),
        ],
        ids=["strict", "loose", "ignored"],
    )
    def test_roundtrip_from_string(self, raw: str, expected: LifecycleValidationMode) -> None:
        assert LifecycleValidationMode(raw) is expected

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            LifecycleValidationMode("unknown")


class TestAppSettings:
    def setup_method(self, monkeypatch: pytest.MonkeyPatch | None = None) -> None:
        self.settings = AppSettings()

    def test_default_testing_is_true(self) -> None:
        assert self.settings.TESTING is True

    def test_default_environment_is_local(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        settings = AppSettings()
        assert settings.ENVIRONMENT == "local"

    def test_default_executor_is_threadpool(self) -> None:
        assert self.settings.EXECUTOR == ExecutorType.THREADPOOL

    def test_default_max_workers_is_5(self) -> None:
        assert self.settings.MAX_WORKERS == 5

    def test_default_log_level_is_debug(self) -> None:
        assert self.settings.LOG_LEVEL == "DEBUG"

    def test_default_enable_distlock_manager_is_true(self) -> None:
        assert self.settings.ENABLE_DISTLOCK_MANAGER is True

    def test_default_distlock_backend_is_memory(self) -> None:
        assert self.settings.DISTLOCK_BACKEND == "memory"

    def test_default_cors_origins_is_wildcard(self) -> None:
        assert self.settings.CORS_ORIGINS == "*"

    def test_default_mail_port_is_25(self) -> None:
        assert self.settings.MAIL_PORT == 25

    def test_default_federation_version_is_2_9(self) -> None:
        assert self.settings.FEDERATION_VERSION == "2.9"

    def test_default_lifecycle_validation_mode_is_loose(self) -> None:
        assert self.settings.LIFECYCLE_VALIDATION_MODE is LifecycleValidationMode.LOOSE

    @pytest.mark.parametrize(
        "method",
        ["GET", "PUT", "PATCH", "POST", "DELETE", "OPTIONS", "HEAD"],
        ids=["GET", "PUT", "PATCH", "POST", "DELETE", "OPTIONS", "HEAD"],
    )
    def test_cors_allow_methods_contains_method(self, method: str) -> None:
        assert method in self.settings.CORS_ALLOW_METHODS

    def test_cors_allow_headers_contains_authorization(self) -> None:
        assert "Authorization" in self.settings.CORS_ALLOW_HEADERS

    def test_cors_expose_headers_contains_etag(self) -> None:
        assert "ETag" in self.settings.CORS_EXPOSE_HEADERS

    def test_session_secret_is_secret_str(self) -> None:
        from pydantic import SecretStr

        assert isinstance(self.settings.SESSION_SECRET, SecretStr)

    def test_session_secret_has_16_char_length(self) -> None:
        assert len(self.settings.SESSION_SECRET.get_secret_value()) == 16

    def test_default_product_workflows_contains_modify_note(self) -> None:
        assert "modify_note" in self.settings.DEFAULT_PRODUCT_WORKFLOWS

    def test_filter_by_mode_default_is_exact(self) -> None:
        assert self.settings.FILTER_BY_MODE == "exact"


class TestAuthorizers:
    def test_default_internal_authorize_callback_is_none(self) -> None:
        auth = Authorizers()
        assert auth.internal_authorize_callback is None

    def test_default_internal_retry_auth_callback_is_none(self) -> None:
        auth = Authorizers()
        assert auth.internal_retry_auth_callback is None

    @pytest.mark.asyncio
    async def test_authorize_callback_returns_true_when_no_internal_callback(self) -> None:
        auth = Authorizers()
        result = await auth.authorize_callback(None)
        assert result is True

    @pytest.mark.asyncio
    async def test_authorize_callback_delegates_to_internal_callback(self) -> None:
        async def _accept(user: object) -> bool:
            return False

        auth = Authorizers(internal_authorize_callback=_accept)
        result = await auth.authorize_callback(None)
        assert result is False

    @pytest.mark.asyncio
    async def test_retry_auth_callback_returns_true_when_no_internal_callback(self) -> None:
        auth = Authorizers()
        result = await auth.retry_auth_callback(None)
        assert result is True

    @pytest.mark.asyncio
    async def test_retry_auth_callback_delegates_to_internal_callback(self) -> None:
        async def _deny(user: object) -> bool:
            return False

        auth = Authorizers(internal_retry_auth_callback=_deny)
        result = await auth.retry_auth_callback(None)
        assert result is False


class TestGetAuthorizers:
    def test_returns_authorizers_instance(self) -> None:
        result = get_authorizers()
        assert isinstance(result, Authorizers)

    def test_returns_same_singleton(self) -> None:
        first = get_authorizers()
        second = get_authorizers()
        assert first is second
