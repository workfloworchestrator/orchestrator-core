import pytest


@pytest.fixture(autouse=True)
def fake_openai_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
