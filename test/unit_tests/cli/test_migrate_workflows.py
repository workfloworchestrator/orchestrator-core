from types import SimpleNamespace
from typing import cast
from unittest import mock

import pytest

import orchestrator.cli.migrate_workflows as migrate_workflows
from orchestrator.workflows import LazyWorkflowInstance


def _state():
    return {"workflows_to_add": [], "workflows_to_delete": []}


def _workflows() -> dict[str, LazyWorkflowInstance]:
    return cast(dict[str, LazyWorkflowInstance], {"create_my_product": object()})


def _patch_product_types(monkeypatch, product_types: list[str]) -> None:
    monkeypatch.setattr(
        migrate_workflows,
        "db",
        SimpleNamespace(session=SimpleNamespace(scalars=lambda _: product_types)),
    )


def _patch_workflow_menus(monkeypatch, *choices: str | None) -> None:
    menu_choices = iter(choices)
    monkeypatch.setattr(migrate_workflows, "_prompt_user_menu", lambda *_args, **_kwargs: next(menu_choices))


def test_add_workflow_returns_state_without_registered_workflows(monkeypatch):
    _patch_product_types(monkeypatch, ["my_product_type"])

    result = migrate_workflows._add_workflow({}, _state())

    assert result == _state()


def test_add_workflow_returns_state_without_registered_product_types(monkeypatch):
    _patch_product_types(monkeypatch, [])

    result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()


def test_add_workflow_returns_state_when_product_menu_cancelled(monkeypatch):
    _patch_product_types(monkeypatch, ["my_product_type"])
    _patch_workflow_menus(monkeypatch, None)

    result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()


def test_add_workflow_returns_state_when_workflow_menu_cancelled(monkeypatch):
    _patch_product_types(monkeypatch, ["my_product_type"])
    _patch_workflow_menus(monkeypatch, "my_product_type", None)

    result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()


@mock.patch("orchestrator.cli.migrate_workflows.get_workflow")
def test_add_workflow_returns_state_when_workflow_cannot_be_loaded(mock_get_workflow, monkeypatch):
    _patch_product_types(monkeypatch, ["my_product_type"])
    _patch_workflow_menus(monkeypatch, "my_product_type", "create_my_product")
    mock_get_workflow.return_value = None

    result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()


@mock.patch("orchestrator.cli.migrate_workflows.get_workflow")
def test_add_workflow_requires_description(mock_get_workflow, monkeypatch):
    _patch_product_types(monkeypatch, ["my_product_type"])
    _patch_workflow_menus(monkeypatch, "my_product_type", "create_my_product")
    mock_get_workflow.return_value = SimpleNamespace(target=SimpleNamespace(value="CREATE"))
    monkeypatch.setattr(migrate_workflows, "get_user_input", lambda *_args, **_kwargs: "")

    result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()


@mock.patch("orchestrator.cli.migrate_workflows.get_workflow")
def test_add_workflow_adds_description(mock_get_workflow, monkeypatch):
    _patch_product_types(monkeypatch, ["my_product_type"])
    _patch_workflow_menus(monkeypatch, "my_product_type", "create_my_product")
    mock_get_workflow.return_value = SimpleNamespace(target=SimpleNamespace(value="CREATE"))
    monkeypatch.setattr(migrate_workflows, "get_user_input", lambda *_args, **_kwargs: "Create my product")

    result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result["workflows_to_add"] == [
        {
            "name": "create_my_product",
            "target": "CREATE",
            "description": "Create my product",
            "product_type": "my_product_type",
        }
    ]


@pytest.mark.parametrize("description", ["", None])
def test_add_workflow_description_guard_handles_empty_and_none(monkeypatch, description):
    _patch_product_types(monkeypatch, ["my_product_type"])
    _patch_workflow_menus(monkeypatch, "my_product_type", "create_my_product")
    monkeypatch.setattr(
        migrate_workflows, "get_workflow", lambda _: SimpleNamespace(target=SimpleNamespace(value="CREATE"))
    )
    monkeypatch.setattr(migrate_workflows, "get_user_input", lambda *_args, **_kwargs: description)

    result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()
