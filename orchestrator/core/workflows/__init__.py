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


from importlib import import_module
from typing import Protocol, runtime_checkable

import structlog
from more_itertools import first

from orchestrator.core.utils.docs import make_workflow_index_doc
from orchestrator.core.workflow import Workflow

logger = structlog.get_logger(__name__)

DEFAULT_PKG = "orchestrator.core.workflows"


ALL_WORKFLOWS: dict[str, "LazyWorkflowInstance"] = {}


class LazyWorkflowInstance:
    """Capture workflow function reference for lazy instantiation.

    Importing all workflow functions into a higher level package was the cause for many circular import problems. To
    remedy this we register each workflow with an instance of this class and only import them when required.

    Importing only is not sufficient as some workflow definitions are created indirectly by helper functions that
    might or might not be parameterized. Hence the usage of the phrase 'instantiation' (which is not entirely
    technically correct, but as my imagination is limited and naming is one of the hard problem in programming,
    that's what it is for now).

    Usage::

        LazyWorkflowInstance(<package ref>, <name>, <is_callable>)

    Both `<package ref>` and `<name>` are strings. `<package ref>` can be an absolute package reference or a
    relative package reference. In case of the latter, the package it is relative to is indicated by the module level
    constant `DEFAULT_PKG`.

    Examples::

         LazyWorkflowInstance(".port", "create")  # from .port import create

    The `".port"` is short for `"server.workflows.port"`. If a different parent package is required, use the
    absolute reference syntax::

        LazyWorkflowInstance("different.package.port", "create")

    """

    package: str
    function: str

    def __init__(self, package: str, name: str) -> None:
        self.package = package
        self.function = name
        ALL_WORKFLOWS[name] = self

    def instantiate(self) -> Workflow:
        """Import and instantiate a workflow and return it.

        This can be as simple as merely importing a workflow function. However, if it concerns a workflow generating
        function, that function will be called with or without arguments as specified.

        Returns:
            A workflow function.

        """
        try:
            if self.package.startswith("."):
                # relative import, hence `package` should be set
                mod = import_module(self.package, package=DEFAULT_PKG)
            else:
                mod = import_module(self.package)
        except ModuleNotFoundError:
            module_name = f"{DEFAULT_PKG}{self.package}" if self.package.startswith(".") else self.package
            raise ValueError(f"Invalid workflow: module {module_name} does not exist or has invalid imports")

        wf = getattr(mod, self.function)

        # Set workflow name here to make them complete
        wf.name = self.function
        return wf

    def __str__(self) -> str:
        return f"{self.package}.{self.function}"

    def __repr__(self) -> str:
        return f"LazyWorkflowInstance('{self.package}','{self.function}')"


@runtime_checkable
class WorkflowSource(Protocol):
    """Provides workflows that are not registered in code with a `LazyWorkflowInstance`, e.g. stored in the database.

    A source is consulted for names that are not in `ALL_WORKFLOWS`, so a workflow defined in code always wins.
    """

    def get(self, name: str) -> Workflow | None:
        """Return the workflow called `name`, or None when this source does not provide it."""
        ...

    def names(self) -> set[str]:
        """Return the names of all workflows this source provides."""
        ...

    def owned_names(self) -> set[str]:
        """Return the names of all `workflows` rows this source manages, including archived (soft deleted) ones.

        Tooling that cleans up rows without a workflow in code must leave these alone.
        """
        ...


WORKFLOW_SOURCES: list[WorkflowSource] = []


def register_workflow_source(source: WorkflowSource) -> None:
    """Make `get_workflow` fall back to `source` for names that are not registered in code."""
    if source not in WORKFLOW_SOURCES:
        WORKFLOW_SOURCES.append(source)


def source_workflow_names() -> set[str]:
    """Names of the workflows provided by registered sources rather than by code."""
    return {name for source in WORKFLOW_SOURCES for name in source.names()}


def source_owned_workflow_names() -> set[str]:
    """Names of every `workflows` row managed by a registered source, including archived ones."""
    return {name for source in WORKFLOW_SOURCES for name in source.owned_names()}


def all_workflow_names() -> set[str]:
    """Names of every workflow that `get_workflow` can resolve."""
    return set(ALL_WORKFLOWS) | source_workflow_names()


def get_workflow(name: str) -> Workflow | None:
    if wi := ALL_WORKFLOWS.get(name):
        return wi.instantiate()

    workflow = first((wf for source in WORKFLOW_SOURCES if (wf := source.get(name)) is not None), None)
    if workflow is None:
        logger.debug("Workflow not found with this name", name=name)
    return workflow


# Modify
LazyWorkflowInstance(".modify_note", "modify_note")

# Tasks
LazyWorkflowInstance(".tasks.cleanup_tasks_log", "task_clean_up_tasks")
LazyWorkflowInstance(".tasks.resume_workflows", "task_resume_workflows")
LazyWorkflowInstance(".tasks.validate_awaiting_callbacks", "task_validate_awaiting_callbacks")
LazyWorkflowInstance(".tasks.validate_products", "task_validate_products")
LazyWorkflowInstance(".tasks.validate_product_type", "task_validate_product_type")
LazyWorkflowInstance(".tasks.validate_subscriptions", "task_validate_subscriptions")

# Workflows designed in the GUI live in the database; registering their source here makes every process resolve them.
from orchestrator.core.workflow_designer.source import designed_workflows  # noqa: E402

register_workflow_source(designed_workflows)

__doc__ = make_workflow_index_doc(ALL_WORKFLOWS)
