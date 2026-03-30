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


def _wf_row(name: str, target: str = "CREATE", description: str = "desc", product_type: str | None = "my_product_type"):
    products = [] if product_type is None else [SimpleNamespace(product_type=product_type)]
    return SimpleNamespace(name=name, target=target, description=description, products=products, is_task=False)


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


@mock.patch("orchestrator.cli.migrate_workflows.get_user_input")
def test_delete_workflow_adds_selected_item(mock_get_user_input):
    workflows = [_wf_row("wf_a", "CREATE", "A", "pt-a")]
    state = _state()
    mock_get_user_input.return_value = "1"

    result = migrate_workflows._delete_workflow(workflows, state)

    assert result["workflows_to_delete"] == [
        {"name": "wf_a", "target": "CREATE", "description": "A", "product_type": "pt-a"}
    ]


@mock.patch("orchestrator.cli.migrate_workflows.get_user_input")
def test_delete_workflow_returns_state_on_invalid_selection(mock_get_user_input):
    workflows = [_wf_row("wf_a")]
    state = _state()
    mock_get_user_input.return_value = "q"

    result = migrate_workflows._delete_workflow(workflows, state)

    assert result == state


@mock.patch("orchestrator.cli.migrate_workflows.get_user_input")
def test_delete_dangling_workflows_cancel_keeps_state(mock_get_user_input):
    workflows = [_wf_row("wf_a")]
    state = _state()
    mock_get_user_input.return_value = "n"

    result = migrate_workflows.delete_dangling_workflows(workflows, state)

    assert result == state


@mock.patch("orchestrator.cli.migrate_workflows.get_user_input")
def test_delete_dangling_workflows_confirm_adds_items(mock_get_user_input):
    workflows = [_wf_row("wf_a", "MODIFY", "to delete", "pt-a")]
    state = _state()
    mock_get_user_input.return_value = "y"

    result = migrate_workflows.delete_dangling_workflows(workflows, state)

    assert result["workflows_to_delete"] == [
        {"name": "wf_a", "target": "MODIFY", "description": "to delete", "product_type": "pt-a"}
    ]


def _make_wizard_exit(abort: bool):
    def exit_choice(state):
        return {**state, "done": True, "abort": abort}

    return exit_choice


@mock.patch("orchestrator.cli.migrate_workflows._prompt_user_menu")
def test_create_workflows_migration_wizard_abort_returns_empty_lists(mock__prompt_user_menu):
    mock__prompt_user_menu.return_value = _make_wizard_exit(abort=True)
    fake_db = SimpleNamespace(session=SimpleNamespace(scalars=lambda *_args, **_kwargs: []))

    with (
        mock.patch.object(migrate_workflows, "db", fake_db),
        mock.patch.object(migrate_workflows.orchestrator.workflows, "ALL_WORKFLOWS", {}),
    ):
        to_add, to_delete = migrate_workflows.create_workflows_migration_wizard()

    assert to_add == []
    assert to_delete == []


@mock.patch("orchestrator.cli.migrate_workflows._prompt_user_menu")
def test_create_workflows_migration_wizard_finish_returns_state_lists(mock__prompt_user_menu):
    mock__prompt_user_menu.return_value = _make_wizard_exit(abort=False)
    fake_db = SimpleNamespace(session=SimpleNamespace(scalars=lambda *_args, **_kwargs: []))

    with (
        mock.patch.object(migrate_workflows, "db", fake_db),
        mock.patch.object(migrate_workflows.orchestrator.workflows, "ALL_WORKFLOWS", {}),
    ):
        to_add, to_delete = migrate_workflows.create_workflows_migration_wizard()

    assert to_add == []
    assert to_delete == []
