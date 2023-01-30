import itertools
from typing import Dict, Iterable, List, Optional, Tuple, TypeVar

import sqlalchemy
import structlog
from tabulate import tabulate

import orchestrator.workflows
from orchestrator.cli.domain_gen_helpers.helpers import get_user_input, sql_compile
from orchestrator.cli.domain_gen_helpers.print_helpers import COLOR, print_fmt, str_fmt
from orchestrator.db import ProductTable, WorkflowTable
from orchestrator.targets import Target
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


def _prompt_user_menu(options: Iterable[Tuple[str, T]], keys: Optional[List[str]] = None, repeat=True) -> T:
    options_list = list(options)
    keys = keys or [str(i + 1) for i in range(len(options_list))]
    done = False
    while not done:
        for k, txt_v in zip(keys, options_list):
            print(f"{k}) {txt_v[0]}")
        choice = get_user_input("? ")
        if choice not in keys:
            print("Invalid choice")
            done = not repeat
        else:
            return options_list[keys.index(choice)][1]


def _print_workflows_table(workflows: List[WorkflowTable]):
    items = [(wf.name, wf.target, wf.description, wf.products[0].product_type) for wf in workflows if wf.products]
    print_fmt(
        tabulate(
            items,
            headers=["#", "name", "target", "description", "product_type"],
            showindex=itertools.count(1),
        ),
        end="\n\n",
    )


def _delete_unregistered_worfklows_sql(workflows: List[WorkflowTable]) -> List[str]:
    if workflows:
        print_fmt(
            "\nThe following workflows were found in the database that do not have a corresponding LazyWorkflowInstance:\n"
        )
        # All workflow products have the same product_type, so we take the first product
        # Workflows without a product (tasks) will not be listed
        _print_workflows_table(workflows)
        should_delete_dangling_workflows = (
            get_user_input("Do you wish to delete all dangling workflows from the database? [Y/n]: ", "n") == "Y"
        )

        if should_delete_dangling_workflows:
            stmt = sqlalchemy.delete(WorkflowTable).filter(WorkflowTable.name.in_([wf.name for wf in workflows])).sql()
            return [str(stmt)]
    return []


def _add_workflow(workflows: Dict[str, LazyWorkflowInstance], state: dict) -> dict:
    print_fmt("\nAdd new workflow\n", flags=[COLOR.UNDERLINE])
    print("Which product type should the workflow be added to?")
    registered_product_types = [
        row[0] for row in ProductTable.query.with_entities(ProductTable.product_type).distinct()
    ]
    product_type = _prompt_user_menu((p, p) for p in registered_product_types)

    print(f"\nAdd product type {str_fmt(product_type, flags=[COLOR.BOLD])} to which workflow?")
    wf_name = _prompt_user_menu((wf, wf) for wf in workflows)
    wf_inst = get_workflow(wf_name)
    wf_target = wf_inst.target
    wf_description = wf_inst.description
    wf_to_add = {"name": wf_name, "target": wf_target, "description": wf_description, "product_type": product_type}
    return {**state, "workflows_to_add": [*state["workflows_to_add"], wf_to_add]}


def _delete_workflow(workflows: List[WorkflowTable], state: dict) -> dict:
    print_fmt("\nDelete existing workflow\n", flags=[COLOR.UNDERLINE])
    items = [(wf.name, wf.target, wf.description, wf.products[0].product_type) for wf in workflows if wf.products]
    print_fmt(
        tabulate(
            items,
            headers=["#", "name", "target", "description", "product_type"],
            showindex=itertools.count(1),
        ),
        end="\n\n",
    )
    wf_num = get_user_input("Which workflow do you want to delete? (q to cancel) ", "q")
    if not wf_num.isdigit():
        return state
    wf_num = int(wf_num)
    if 0 < wf_num < len(items) + 1:
        return {**state, "workflows_to_delete": [*state["workflows_to_delete"], workflows[wf_num].name]}
    else:
        return state


def create_workflows_migration_sql(is_test: bool = False) -> Tuple[List[str], List[str]]:
    """Create tuple with list for upgrade and downgrade SQL statements based on #TODO.

    You will be prompted with inputs for new models and resource type updates.

    Args:
        - inputs: dict with pre-defined input values

    Returns tuple:
        - list of upgrade SQL statements in string format.
        - list of downgrade SQL statements in string format.
    """
    database_workflows = WorkflowTable.query
    registered_workflows = orchestrator.workflows.ALL_WORKFLOWS
    system_workflow_names = {wf.name for wf in database_workflows if wf.target == Target.SYSTEM}
    print("SYSTEM", system_workflow_names)
    registered_non_system_workflows = {k: v for k, v in registered_workflows.items() if k not in system_workflow_names}

    unregistered_workflows = [wf for wf in database_workflows if wf.name not in registered_workflows.keys()]

    print("Registered", registered_workflows.keys())
    print("DATABASE", database_workflows)
    print("Unregistered", unregistered_workflows, len(unregistered_workflows))

    # stmts = _delete_unregistered_worfklows_sql(unregistered_workflows)
    stmts = []

    # Main menu loop
    state = {"workflows_to_add": [], "workflows_to_delete": [], "done": False}
    while not state["done"]:
        print("State:", state)
        print_fmt("\nWhat do you want to do?\n", flags=[COLOR.UNDERLINE, COLOR.BOLD])
        choice_fn = _prompt_user_menu(
            [
                ("Add workflow to database", lambda: _add_workflow(registered_non_system_workflows, state)),
                ("Delete workflow from database", lambda: _delete_workflow(database_workflows, state)),
                ("Finish and create migration file", lambda: {**state, "done": True, "abort": False}),
                ("Abort and quit without creating a migration file", lambda: {**state, "done": True, "abort": True}),
            ],
            keys=["a", "b", "c", "q"],
        )
        state = choice_fn()

    print("Finished main loop", state)
    if state.get("abort"):
        return [], []

    logger.info("Create workflows", create_workflows=state["workflows_to_add"])
    logger.info("Delete workflows", delete_workflows=state["workflows_to_delete"])

    sql_upgrade_stmts = []
    sql_downgrade_stmts = []
    return sql_upgrade_stmts, sql_downgrade_stmts
