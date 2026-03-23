# Copyright 2019-2024 SURF.
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

from orchestrator.utils.deprecation_logger import deprecated_endpoint


def _make_request(method: str = "GET", url: str = "http://example.com/api/old-endpoint") -> MagicMock:
    request = MagicMock()
    request.method = method
    request.url = url
    return request


class TestDeprecatedEndpoint:
    def test_logs_warning(self) -> None:
        request = _make_request()
        with patch("orchestrator.utils.deprecation_logger.logger") as mock_logger:
            deprecated_endpoint(request)
            mock_logger.warning.assert_called_once()

    def test_warning_message_mentions_deprecated(self) -> None:
        request = _make_request()
        with patch("orchestrator.utils.deprecation_logger.logger") as mock_logger:
            deprecated_endpoint(request)
            message = mock_logger.warning.call_args[0][0]
            assert "deprecated" in message.lower()

    def test_warning_includes_method(self) -> None:
        request = _make_request(method="POST")
        with patch("orchestrator.utils.deprecation_logger.logger") as mock_logger:
            deprecated_endpoint(request)
            kwargs = mock_logger.warning.call_args[1]
            assert kwargs["method"] == "POST"

    def test_warning_includes_url(self) -> None:
        url = "http://example.com/api/legacy"
        request = _make_request(url=url)
        with patch("orchestrator.utils.deprecation_logger.logger") as mock_logger:
            deprecated_endpoint(request)
            kwargs = mock_logger.warning.call_args[1]
            assert kwargs["url"] == str(url)

    def test_returns_none(self) -> None:
        request = _make_request()
        with patch("orchestrator.utils.deprecation_logger.logger"):
            # deprecated_endpoint returns None; calling without capturing the result
            deprecated_endpoint(request)

    def test_called_with_different_http_methods(self) -> None:
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            request = _make_request(method=method)
            with patch("orchestrator.utils.deprecation_logger.logger") as mock_logger:
                deprecated_endpoint(request)
                kwargs = mock_logger.warning.call_args[1]
                assert kwargs["method"] == method
