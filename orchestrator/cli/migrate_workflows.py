import itertools
import operator
from collections.abc import Iterable
from typing import TypeVar

import structlog
from sqlalchemy import select
from tabulate import tabulate

import orchestrator.workflows
from orchestrator.cli.helpers.input_helpers import _enumerate_menu_keys, _prompt_user_menu, get_user_input
from orchestrator.cli.helpers.print_helpers import COLOR, noqa_print, print_fmt, str_fmt
from orchestrator.db import ProductTable, WorkflowTable, db
from orchestrator.workflows import LazyWorkflowInstance, get_workflow

# Workflows are registered via migrations with product type. For every product with the given product_type, there will be an entry in products_workflows.
# So the relationship product_type <-> workflow has cardinality 1 <-> *.  You can have zero or more workflows for a product_type, but every workflow has 1 product_type.
# This is not evident in the db schema and we need to manually maintain this relation via the code for it to be consistent.

# The workflows, products, product_blocks, product_product_blocks and products_workflows tables are all managed by code and migration files
# New workflows are added with migration files, so they can be removed with migration files as well
# We can assume that production environments are always test envs in terms of migrations executed. It is therefore ok use workflow names in the migration files, since
# the database should only contain workflow names added from previous migration files.

# Workflows without a product associated (tasks) should not be removed

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def _print_workflows_table(workflows: list[WorkflowTable]) -> None:
    items = [(wf.name, wf.target, wf.description, wf.products[0].product_type) for wf in workflows if wf.products]
    print_fmt(
        tabulate(
            items,
            headers=["#", "name", "target", "description", "product_type"],
            showindex=itertools.count(1),
        ),
        end="\n\n",
    )


def _add_workflow(workflows: dict[str, LazyWorkflowInstance], state: dict) -> dict:
    print_fmt("\nAdd new workflow\n", flags=[COLOR.UNDERLINE])

    if not workflows:
        noqa_print("No registered workflows found to add to the database")
        return state

    registered_product_types = list(db.session.scalars(select(ProductTable.product_type).distinct()))
    if not registered_product_types:
        noqa_print("No registered product types found")
        return state

    noqa_print("Which product type should the workflow be added to?")
    product_type = _prompt_user_menu(
        [*[(p, p) for p in registered_product_types], ("cancel", None)],
        keys=[*_enumerate_menu_keys(registered_product_types), "q"],
    )

    if not product_type:
        # Menu cancelled
        return state

    noqa_print(f"\nAdd product type {str_fmt(product_type, flags=[COLOR.BOLD])} to which workflow?")

    already_used_workflows = {wf["name"] for wf in state["workflows_to_add"] + state["workflows_to_delete"]}
    wf_options = [(wf, wf) for wf in workflows if wf not in already_used_workflows]
    wf_name = _prompt_user_menu([*wf_options, ("cancel", None)], keys=[*_enumerate_menu_keys(wf_options), "q"])
    if not wf_name:
        # Menu cancelled
        return state

    wf_inst = get_workflow(wf_name)
    if wf_inst is None:
        # Error getting workflow
        noqa_print("Could not load workflow")
        return state

    wf_target = wf_inst.target.value if wf_inst.target is not None else None
    wf_description = wf_inst.description
    wf_to_add = {"name": wf_name, "target": wf_target, "description": wf_description, "product_type": product_type}
    return {**state, "workflows_to_add": [*state["workflows_to_add"], wf_to_add]}


def _delete_workflow(workflows: Iterable[WorkflowTable], state: dict) -> dict:
    print_fmt("\nDelete existing workflow\n", flags=[COLOR.UNDERLINE])
    already_used_workflows = {wf["name"] for wf in state["workflows_to_add"] + state["workflows_to_delete"]}
    items = [
        (wf.name, wf.target, wf.description, wf.products[0].product_type)
        for wf in workflows
        if wf.products and wf.name not in already_used_workflows
    ]
    items = sorted(items, key=operator.itemgetter(3, 1))
    keys = ["#", "name", "target", "description", "product_type"]
    if not items:
        noqa_print("No deletable workflows in database")
        return state

    print_fmt(
        tabulate(
            items,
            headers=keys,
            showindex=itertools.count(1),
        ),
        end="\n\n",
    )
    wf_num = get_user_input("Which workflow do you want to delete? (q to cancel) ", "q")
    if not wf_num.isdigit():
        return state
    wf_index = int(wf_num) - 1
    if 0 <= wf_index < len(items):
        item = dict(zip(keys[1:], items[wf_index]))
        return {**state, "workflows_to_delete": [*state["workflows_to_delete"], item]}
    return state


def _show_state(state: dict) -> dict:
    print_fmt("\nWorkflows to add:", flags=[COLOR.GREEN])
    print_fmt(
        tabulate(
            state["workflows_to_add"],
            headers="keys",
            showindex=itertools.count(1),
        ),
        end="\n\n",
    )

    print_fmt("Workflows to delete:", flags=[COLOR.RED])
    print_fmt(
        tabulate(
            state["workflows_to_delete"],
            headers="keys",
            showindex=itertools.count(1),
        ),
        end="\n\n",
    )
    return state


def delete_dangling_workflows(workflows: list[WorkflowTable], state: dict) -> dict:
    if not workflows:
        noqa_print("No dangling workflows found.")
        return state

    print_fmt(
        "\nThe following workflows were found in the database that do not have a corresponding LazyWorkflowInstance:\n"
    )
    # All workflow products have the same product_type, so we take the first product
    # Workflows without a product  will not be listed
    _print_workflows_table(workflows)
    should_delete_dangling_workflows = (
        get_user_input("Do you wish to delete all dangling workflows from the database? [y/n]: ", "n").lower() == "y"
    )

    if not should_delete_dangling_workflows:
        noqa_print("Cancelling")
        return state

    already_used_workflows = {wf["name"] for wf in state["workflows_to_add"] + state["workflows_to_delete"]}
    keys = ["name", "target", "description", "product_type"]
    items = [
        {
            "name": wf.name,
            "target": wf.target,
            "description": wf.description,
            "product_type": wf.products[0].product_type,
        }
        for k, wf in zip(keys, workflows)
        if wf.products and wf.name not in already_used_workflows
    ]
    return {**state, "workflows_to_delete": [*state["workflows_to_delete"], *items]}


def create_workflows_migration_wizard() -> tuple[list[dict], list[dict]]:
    """Create tuple with lists for workflows to add and delete.

    Returns tuple:
        - list of workflow items to add in the migration
        - list of workflow items to delete in the migration
    """
    database_workflows = list(db.session.scalars(select(WorkflowTable)))
    registered_workflows = orchestrator.workflows.ALL_WORKFLOWS
    system_workflow_names = {wf.name for wf in database_workflows if wf.is_task}
    registered_non_system_workflows = {k: v for k, v in registered_workflows.items() if k not in system_workflow_names}

    unregistered_workflows = [wf for wf in database_workflows if wf.name not in registered_workflows.keys()]

    # Main menu loop
    state = {"workflows_to_add": [], "workflows_to_delete": [], "done": False}
    while not state["done"]:
        print_fmt("\nWhat do you want to do?\n", flags=[COLOR.UNDERLINE, COLOR.BOLD])
        choice_fn = _prompt_user_menu(
            [
                ("Add workflow to database", lambda s: _add_workflow(registered_non_system_workflows, s)),
                ("Delete workflow from database", lambda s: _delete_workflow(database_workflows, s)),
                (
                    "Delete unregistered workflows from database",
                    lambda s: delete_dangling_workflows(unregistered_workflows, s),
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

    logger.info("Create workflows", create_workflows=state["workflows_to_add"])
    logger.info("Delete workflows", delete_workflows=state["workflows_to_delete"])

    return state["workflows_to_add"], state["workflows_to_delete"]  # type: ignore
