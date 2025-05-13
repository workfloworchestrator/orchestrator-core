# Copyright 2019-2025 SURF, GÉANT.
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

import itertools
import operator
from collections.abc import Iterable
from typing import TypeVar, cast

import structlog
from sqlalchemy import select
from tabulate import tabulate

import orchestrator.workflows
from orchestrator.cli.helpers.input_helpers import _enumerate_menu_keys, _prompt_user_menu, get_user_input
from orchestrator.cli.helpers.print_helpers import COLOR, noqa_print, print_fmt
from orchestrator.db import WorkflowTable, db
from orchestrator.targets import Target
from orchestrator.workflow import Workflow
from orchestrator.workflows import get_workflow

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def _print_tasks_table(tasks: list[WorkflowTable]) -> None:
    items = [(task.name, task.description) for task in tasks]
    print_fmt(
        tabulate(
            items,
            headers=["#", "name", "description"],
            showindex=itertools.count(1),
        ),
        end="\n\n",
    )


def _add_task(tasks: dict[str, Workflow], state: dict) -> dict:
    print_fmt("\nAdd new task\n", flags=[COLOR.UNDERLINE])

    if not tasks:
        noqa_print("No registered tasks found to add to the database")
        return state

    noqa_print("\nWhich task should be added?")

    already_used_tasks = {task["name"] for task in state["tasks_to_add"] + state["tasks_to_delete"]}
    task_options = [(task, task) for task in tasks.keys() if task not in already_used_tasks]
    task_name = _prompt_user_menu([*task_options, ("cancel", None)], keys=[*_enumerate_menu_keys(task_options), "q"])
    if not task_name:
        # Menu cancelled
        return state

    task_to_add = {"name": task_name, "description": tasks[task_name].description}
    return {**state, "tasks_to_add": [*state["tasks_to_add"], task_to_add]}


def _delete_task(tasks: Iterable[WorkflowTable], state: dict) -> dict:
    print_fmt("\nDelete existing task\n", flags=[COLOR.UNDERLINE])
    already_used_tasks = {task["name"] for task in state["tasks_to_add"] + state["tasks_to_delete"]}
    items = [(task.name, task.description) for task in tasks if task not in already_used_tasks]
    items = sorted(items, key=operator.itemgetter(1, 1))
    keys = ["#", "name", "description"]
    if not items:
        noqa_print("No deletable tasks in database")
        return state

    print_fmt(
        tabulate(
            items,
            headers=keys,
            showindex=itertools.count(1),
        ),
        end="\n\n",
    )
    task_num = get_user_input("Which task do you want to delete? (q to cancel) ", "q")
    if not task_num.isdigit():
        return state
    task_index = int(task_num) - 1
    if 0 <= task_index < len(items):
        item = dict(zip(keys[1:], items[task_index]))
        return {**state, "tasks_to_delete": [*state["tasks_to_delete"], item]}
    return state


def _show_state(state: dict) -> dict:
    print_fmt("\nTasks to add:", flags=[COLOR.GREEN])
    print_fmt(
        tabulate(
            state["tasks_to_add"],
            headers="keys",
            showindex=itertools.count(1),
        ),
        end="\n\n",
    )

    print_fmt("Tasks to delete:", flags=[COLOR.RED])
    print_fmt(
        tabulate(
            state["tasks_to_delete"],
            headers="keys",
            showindex=itertools.count(1),
        ),
        end="\n\n",
    )
    return state


def delete_dangling_tasks(tasks: list[WorkflowTable], state: dict) -> dict:
    if not tasks:
        noqa_print("No dangling tasks found.")
        return state

    print_fmt(
        "\nThe following tasks were found in the database that do not have a corresponding LazyWorkflowInstance:\n"
    )
    _print_tasks_table(tasks)
    should_delete_dangling_tasks = (
        get_user_input("Do you wish to delete all dangling tasks from the database? [y/n]: ", "n").lower() == "y"
    )

    if not should_delete_dangling_tasks:
        noqa_print("Cancelling")
        return state

    already_used_tasks = {task["name"] for task in state["tasks_to_add"] + state["tasks_to_delete"]}
    keys = ["name", "description"]
    items = [
        {"name": task.name, "description": task.description}
        for k, task in zip(keys, tasks)
        if task.name not in already_used_tasks
    ]
    return {**state, "tasks_to_delete": [*state["tasks_to_delete"], *items]}


def create_tasks_migration_wizard() -> tuple[list[dict], list[dict]]:
    """Create tuple with lists for tasks to add and delete.

    Returns tuple:
        - list of task items to add in the migration
        - list of task items to delete in the migration
    """
    database_tasks = {task.name: task for task in list(db.session.scalars(select(WorkflowTable))) if task.is_task}
    registered_wf_instances = {
        task: cast(Workflow, get_workflow(task)) for task in orchestrator.workflows.ALL_WORKFLOWS.keys()
    }

    is_task = [Target.SYSTEM, Target.VALIDATE]

    registered_tasks = dict(
        filter(
            lambda task: task[1].target in is_task and task[0] in database_tasks.keys(),
            registered_wf_instances.items(),
        )
    )
    available_tasks = dict(
        filter(
            lambda task: task[1].target in is_task and task[0] not in database_tasks.keys(),
            registered_wf_instances.items(),
        )
    )
    unregistered_tasks = [task for task in database_tasks.values() if task.name not in registered_tasks.keys()]

    # Main menu loop
    state = {"tasks_to_add": [], "tasks_to_delete": [], "done": False}
    while not state["done"]:
        print_fmt("\nWhat do you want to do?\n", flags=[COLOR.UNDERLINE, COLOR.BOLD])
        choice_fn = _prompt_user_menu(
            [
                ("Add task to database", lambda s: _add_task(available_tasks, s)),
                ("Delete task from database", lambda s: _delete_task(database_tasks.values(), s)),
                (
                    "Delete unregistered tasks from database",
                    lambda s: delete_dangling_tasks(unregistered_tasks, s),
                ),
                ("Finish and create migration file", lambda s: {**s, "done": True, "abort": False}),
                ("Show current diff", _show_state),
                ("Quit menu without creating a migration file", lambda s: {**s, "done": True, "abort": True}),
            ],
            keys=["a", "x", "c", "y", "d", "q"],
        )
        if choice_fn:
            state = choice_fn(state)  # type: ignore

    if state.get("abort"):
        return [], []

    logger.info("Create tasks", create_tasks=state["tasks_to_add"])
    logger.info("Delete tasks", delete_tasks=state["tasks_to_delete"])

    return state["tasks_to_add"], state["tasks_to_delete"]  # type: ignore
