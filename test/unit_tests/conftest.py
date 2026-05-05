# Copyright 2019-2026 SURF, GÉANT.
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

"""Unit-test conftest.

Pure unit tests run with no Postgres, no Redis, no FastAPI app, no scheduler,
no migrations and no Celery. Fixtures registered here must respect that contract.

Heavy fixtures (DB sessions, app bootstrap, product/subscription factories) live
in ``test/integration_tests/conftest.py``.
"""

from typing import Any

import pytest
import requests  # noqa: F401  # intentional: ensures `requests` is importable for HTTP-mocking tests
from pydantic import BaseModel as PydanticBaseModel
from urllib3_mock import Responses

from orchestrator.core.services.translations import generate_translations
from pydantic_forms.core import FormPage


@pytest.fixture(autouse=True)
def reset_worker_monitor_state():
    """Reset worker monitor state between tests to prevent count leaking across tests.

    The monitor is a session-scoped singleton. Tests that run actual workflows leave
    _active_threadpool_jobs > 0, which the background thread caches. This fixture
    resets that state after each test so the next test starts with an accurate count of 0.
    """
    import orchestrator.core.services.processes as proc_module
    import orchestrator.core.services.worker_status_monitor as wsm_module

    yield

    # Reset the active jobs counter so the monitor reflects reality (no jobs running between tests)
    with proc_module._active_jobs_lock:
        proc_module._active_threadpool_jobs = 0

    # Force the monitor to refresh its cache immediately with the reset value
    if wsm_module._monitor is not None and wsm_module._monitor.is_alive():
        wsm_module._monitor._refresh_once()


@pytest.fixture(autouse=True)
def responses(request):
    if request.node.get_closest_marker("noresponses"):
        # This test doesn't want responses mocking
        yield None
        return
    responses_mock = Responses("requests.packages.urllib3")

    def _find_request(call):
        mock_url = responses_mock._find_match(call.request)
        if not mock_url:
            raise Exception(f"Call not mocked: {call.request}")
        return mock_url

    def _to_tuple(url_mock):
        return (url_mock["url"], url_mock["method"], url_mock["match_querystring"])

    with responses_mock:
        yield responses_mock

        mocked_urls = map(_to_tuple, responses_mock._urls)
        used_urls = map(_to_tuple, map(_find_request, responses_mock.calls))
        not_used = set(mocked_urls) - set(used_urls)
        if not_used:
            pytest.fail(f"Found unused responses mocks: {not_used}", pytrace=False)


@pytest.fixture(scope="session", autouse=True)
def test_form_translations(worker_id):
    """Some voodoo to check for each form during test if the translations are complete."""

    translations = generate_translations("en-GB")["forms"]["fields"]
    used_translations = set()

    # In order to properly wrap a classmethod we need to do special stuff
    old_init_subclass = FormPage.__dict__.get("__pydantic_init_subclass__")  # pydantic < 2.12
    old_on_complete = FormPage.__dict__.get("__pydantic_on_complete__")  # pydantic >= 2.12

    # Wrap a form function that is certain to be called to extract the used form fields
    @classmethod
    def init_subclass_wrapper(cls: type[PydanticBaseModel], *args, **kwargs: Any) -> None:
        # Skip forms in test modules
        if "test" not in cls.__module__:
            for field_name in cls.model_fields:
                used_translations.add(field_name)
                if field_name not in translations and f"{field_name}_accept" not in translations:
                    pytest.fail(f"Missing translation for field {field_name} in  {cls.__name__}")

        # Because the original is a classmethod we need to conform to the descriptor protocol
        if old_init_subclass:
            return old_init_subclass.__get__(None, cls)(*args, **kwargs)
        return old_on_complete.__get__(None, cls)()

    FormPage.__pydantic_init_subclass__ = init_subclass_wrapper
    try:
        yield
    finally:
        # unwrapp and check if all translations are actually used
        FormPage.__pydantic_init_subclass__ = old_init_subclass

        # This check only works when you run without python-xdist because we need one single session
        # TODO this does not work reliable yet
        # if worker_id == "master":
        #     unused_keys = set()
        #     for trans_key in translations:
        #         if (
        #             not trans_key.endswith("_info")
        #             and not trans_key.endswith("_accept")
        #             and not trans_key.endswith("_fields")
        #             and trans_key not in used_translations
        #             and f"{trans_key}_accept" not in used_translations
        #         ):
        #             unused_keys.add(trans_key)

        #     if unused_keys:
        #         pytest.fail(f"found unused translations: {sorted(unused_keys)}", pytrace=False)
