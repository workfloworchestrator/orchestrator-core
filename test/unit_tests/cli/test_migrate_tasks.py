"""Tests for CLI migrate_tasks: task discovery, workflow migration, and task registration."""

from types import SimpleNamespace
from unittest import mock

import pytest

import orchestrator.cli.migrate_tasks as migrate_tasks
import orchestrator.workflows


def _state():
    return {"tasks_to_add": [], "tasks_to_delete": []}


def _mock_task_menus(*choices: str | None):
    menu_choices = iter(choices)
    return mock.patch.object(
        migrate_tasks, "_prompt_user_menu", side_effect=lambda *_args, **_kwargs: next(menu_choices)
    )


class _TaskRow:
    """Lightweight mock for WorkflowTable that supports hash/eq for set membership checks."""

    def __init__(self, name: str, target: str = "SYSTEM", description: str = "desc"):
        self.name = name
        self.target = target
        self.description = description
        self.is_task = True

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _TaskRow):
            return self.name == other.name
        return NotImplemented


def _task_row(name: str, target: str = "SYSTEM", description: str = "desc"):
    return _TaskRow(name=name, target=target, description=description)


# --- _add_task ---


def test_add_task_no_tasks_returns_state():
    state = _state()
    result = migrate_tasks._add_task({}, state)
    assert result == state


def test_add_task_menu_cancelled_returns_state():
    state = _state()
    task = SimpleNamespace(description="My task desc")
    with _mock_task_menus(None):
        result = migrate_tasks._add_task({"validate_my_product": task}, state)
    assert result == state


def test_add_task_valid_selection_adds_to_state():
    state = _state()
    task = SimpleNamespace(description="My task desc")
    with _mock_task_menus("validate_my_product"):
        result = migrate_tasks._add_task({"validate_my_product": task}, state)
    assert result["tasks_to_add"] == [{"name": "validate_my_product", "description": "My task desc"}]


def test_add_task_skips_already_used_tasks():
    state = {**_state(), "tasks_to_add": [{"name": "validate_my_product", "description": "desc"}]}
    task_a = SimpleNamespace(description="My task desc")
    task_b = SimpleNamespace(description="Other task desc")
    with mock.patch.object(migrate_tasks, "_prompt_user_menu") as mock_menu:
        mock_menu.return_value = "other_task"
        result = migrate_tasks._add_task({"validate_my_product": task_a, "other_task": task_b}, state)
    # validate_my_product should not appear in options passed to menu
    call_args = mock_menu.call_args[0][0]
    option_values = [v for _, v in call_args if v is not None]
    assert "validate_my_product" not in option_values
    assert result["tasks_to_add"][-1] == {"name": "other_task", "description": "Other task desc"}


# --- _delete_task ---


def test_delete_task_no_deletable_tasks_returns_state():
    state = _state()
    result = migrate_tasks._delete_task([], state)
    assert result == state


def test_delete_task_valid_selection_deletes_task():
    state = _state()
    tasks = [_task_row("validate_my_product", description="desc")]
    with mock.patch.object(migrate_tasks, "get_user_input", return_value="1"):
        result = migrate_tasks._delete_task(tasks, state)
    assert len(result["tasks_to_delete"]) == 1
    assert result["tasks_to_delete"][0]["name"] == "validate_my_product"


@pytest.mark.parametrize(
    "user_input",
    [
        pytest.param("q", id="cancel"),
        pytest.param("99", id="out-of-range"),
    ],
)
def test_delete_task_invalid_input_returns_state(user_input: str):
    state = _state()
    tasks = [_task_row("validate_my_product", description="desc")]
    with mock.patch.object(migrate_tasks, "get_user_input", return_value=user_input):
        result = migrate_tasks._delete_task(tasks, state)
    assert result == state


# --- _show_state ---


def test_show_state_returns_unchanged_state():
    state = {"tasks_to_add": [{"name": "t", "description": "d"}], "tasks_to_delete": []}
    result = migrate_tasks._show_state(state)
    assert result == state


# --- delete_dangling_tasks ---


def test_delete_dangling_tasks_empty_list_returns_state():
    state = _state()
    result = migrate_tasks.delete_dangling_tasks([], state)
    assert result == state


def test_delete_dangling_tasks_cancel_returns_state():
    state = _state()
    tasks = [_task_row("orphan_task")]
    with mock.patch.object(migrate_tasks, "get_user_input", return_value="n"):
        result = migrate_tasks.delete_dangling_tasks(tasks, state)
    assert result == state


def test_delete_dangling_tasks_confirm_adds_tasks():
    state = _state()
    # Note: the zip(keys, tasks) bug truncates to min(len(keys), len(tasks)) = 2 items
    # keys = ["name", "description"], so only 2 tasks will be added regardless of list length
    tasks = [_task_row("orphan_a"), _task_row("orphan_b"), _task_row("orphan_c")]
    with mock.patch.object(migrate_tasks, "get_user_input", return_value="y"):
        result = migrate_tasks.delete_dangling_tasks(tasks, state)
    # Due to zip(keys, tasks) where keys has 2 elements, only 2 tasks are processed
    assert len(result["tasks_to_delete"]) == 2


# --- create_tasks_migration_wizard ---


def _mock_db_tasks(tasks):
    return mock.patch.object(
        migrate_tasks,
        "db",
        SimpleNamespace(session=SimpleNamespace(scalars=lambda _: tasks)),
    )


def _mock_all_workflows(workflow_names: list[str]):
    return mock.patch.dict(
        orchestrator.workflows.ALL_WORKFLOWS,
        {name: object() for name in workflow_names},
        clear=True,
    )


@pytest.mark.parametrize(
    "abort",
    [
        pytest.param(True, id="abort"),
        pytest.param(False, id="finish"),
    ],
)
def test_create_tasks_migration_wizard_returns_empty(abort: bool):
    with (
        _mock_db_tasks([]),
        _mock_all_workflows([]),
        mock.patch.object(migrate_tasks, "get_workflow", return_value=None),
        mock.patch.object(
            migrate_tasks, "_prompt_user_menu", side_effect=lambda s, **kw: {**s, "done": True, "abort": abort}
        ),
    ):
        tasks_to_add, tasks_to_delete = migrate_tasks.create_tasks_migration_wizard()
    assert tasks_to_add == []
    assert tasks_to_delete == []
