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


def _mock_product_types(product_types: list[str]):
    return mock.patch.object(
        migrate_workflows,
        "db",
        SimpleNamespace(session=SimpleNamespace(scalars=lambda _: product_types)),
    )


def _mock_workflow_menus(*choices: str | None):
    menu_choices = iter(choices)
    return mock.patch.object(
        migrate_workflows, "_prompt_user_menu", side_effect=lambda *_args, **_kwargs: next(menu_choices)
    )


def test_add_workflow_returns_state_without_registered_workflows():
    with _mock_product_types(["my_product_type"]):
        result = migrate_workflows._add_workflow({}, _state())

    assert result == _state()


def test_add_workflow_returns_state_without_registered_product_types():
    with _mock_product_types([]):
        result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()


def test_add_workflow_returns_state_when_product_menu_cancelled():
    with _mock_product_types(["my_product_type"]), _mock_workflow_menus(None):
        result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()


def test_add_workflow_returns_state_when_workflow_menu_cancelled():
    with _mock_product_types(["my_product_type"]), _mock_workflow_menus("my_product_type", None):
        result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()


@mock.patch("orchestrator.cli.migrate_workflows.get_workflow")
def test_add_workflow_returns_state_when_workflow_cannot_be_loaded(mock_get_workflow):
    with _mock_product_types(["my_product_type"]), _mock_workflow_menus("my_product_type", "create_my_product"):
        mock_get_workflow.return_value = None
        result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()


@mock.patch("orchestrator.cli.migrate_workflows.get_user_input")
@mock.patch("orchestrator.cli.migrate_workflows.get_workflow")
def test_add_workflow_requires_description(mock_get_workflow, mock_get_user_input):
    with _mock_product_types(["my_product_type"]), _mock_workflow_menus("my_product_type", "create_my_product"):
        mock_get_workflow.return_value = SimpleNamespace(target=SimpleNamespace(value="CREATE"))
        mock_get_user_input.return_value = ""
        result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()


@mock.patch("orchestrator.cli.migrate_workflows.get_user_input")
@mock.patch("orchestrator.cli.migrate_workflows.get_workflow")
def test_add_workflow_adds_description(mock_get_workflow, mock_get_user_input):
    with _mock_product_types(["my_product_type"]), _mock_workflow_menus("my_product_type", "create_my_product"):
        mock_get_workflow.return_value = SimpleNamespace(target=SimpleNamespace(value="CREATE"))
        mock_get_user_input.return_value = "Create my product"
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
@mock.patch("orchestrator.cli.migrate_workflows.get_user_input")
@mock.patch("orchestrator.cli.migrate_workflows.get_workflow")
def test_add_workflow_description_guard_handles_empty_and_none(mock_get_workflow, mock_get_user_input, description):
    with _mock_product_types(["my_product_type"]), _mock_workflow_menus("my_product_type", "create_my_product"):
        mock_get_workflow.return_value = SimpleNamespace(target=SimpleNamespace(value="CREATE"))
        mock_get_user_input.return_value = description
        result = migrate_workflows._add_workflow(_workflows(), _state())

    assert result == _state()
