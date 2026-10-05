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

"""Discover the steps that exist in code and describe their interface.

Steps have no registry of their own: they are module level objects created by `@step`, `@retrystep` and
`@inputstep`. Discovery imports the configured packages and collects every attribute that is a `Step`. A step is
addressed as ``module:attribute`` because step names and function names are both reused throughout the codebase.
Steps that only exist inside a factory or a `conditional`/`step_group` wrapper have no such address and are left out.
"""

import ast
import importlib
import inspect
import pkgutil
import textwrap
import threading
import time
from collections.abc import Callable, Iterable
from types import ModuleType
from typing import Any, Literal, get_args

import structlog
from pydantic import BaseModel
from sqlalchemy import select

from orchestrator.core.db import ProductTable, db
from orchestrator.core.db.database import transactional
from orchestrator.core.domain import SubscriptionModel
from orchestrator.core.settings import app_settings
from orchestrator.core.utils.functional import orig
from orchestrator.core.workflow import Step
from orchestrator.core.workflow_designer.inference import StateKey, infer_outputs
from orchestrator.core.workflow_designer.type_refs import TypeRef, type_ref_for
from orchestrator.core.workflows import ALL_WORKFLOWS

logger = structlog.get_logger(__name__)

StepKind = Literal["step", "retrystep", "inputstep", "helper"]
InputSource = Literal["state", "subscription_model", "whole_state"]


class StepInput(BaseModel):
    name: str
    type: TypeRef
    annotation: str
    required: bool
    default: Any = None
    source: InputSource = "state"


class StepInfo(BaseModel):
    id: str
    name: str
    function: str
    module: str
    category: str
    description: str = ""
    kind: StepKind
    inputs: list[StepInput] = []
    outputs: list[StateKey] = []
    outputs_known: bool = True
    usable: bool = True
    unusable_reason: str | None = None
    writes_subscription: bool = False
    uses_subscription_models: bool = False
    used_in_workflows: list[str] = []
    config_schema: dict[str, Any] | None = None
    config_defaults: dict[str, Any] | None = None
    pauses: bool = False


def step_kind(step: Step) -> StepKind:
    # `@inputstep` sets a form; `@step` and `@retrystep` are told apart by the closure that wraps the function.
    if step.form is not None:
        return "inputstep"
    qualname = getattr(getattr(step, "__code__", None), "co_qualname", "")
    return "retrystep" if qualname.startswith("retrystep.") else "step"


def iter_modules(packages: Iterable[str]) -> list[ModuleType]:
    modules = []
    for package_name in packages:
        package = importlib.import_module(package_name)
        modules.append(package)
        for module_info in pkgutil.walk_packages(package.__path__, f"{package_name}."):
            try:
                modules.append(importlib.import_module(module_info.name))
            except Exception as exc:  # A broken module should not hide the steps of every other module.
                logger.warning("Skipping module that fails to import", module=module_info.name, error=str(exc))
    return modules


def _annotation_source(func: Callable) -> dict[str, str]:
    """Annotation text per parameter, which keeps aliases like `UUIDstr` that are lost on the annotation object."""
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(func))).body[0]
    except (OSError, TypeError, SyntaxError, IndexError):
        return {}
    if not isinstance(tree, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return {}
    arguments = [*tree.args.posonlyargs, *tree.args.args, *tree.args.kwonlyargs]
    return {arg.arg: ast.unparse(arg.annotation) for arg in arguments if arg.annotation is not None}


def _is_subscription_model(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, SubscriptionModel)


def _annotation_label(annotation: Any, source: str | None) -> str:
    if source:
        return source
    if annotation is inspect.Parameter.empty:
        return "Any"
    return getattr(annotation, "__name__", str(annotation))


def _unusable_reason(step: Step, parameters: list[inspect.Parameter]) -> str | None:
    if step.form is not None:
        return "input steps ask the user for data in the middle of a run; use the 'Ask for confirmation' helper"
    if any(param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD) for param in parameters):
        return "takes *args/**kwargs, so its inputs cannot be determined"
    if any(param.name == "state" for param in parameters):
        return "reads the whole state, so its inputs cannot be determined"
    return None


def _without_optional(annotation: Any) -> Any:
    """The annotation without `Optional`, so `Model | None` is recognised as a domain model parameter."""
    args = [arg for arg in get_args(annotation) if arg is not type(None)]
    return args[0] if len(args) == 1 and type(None) in get_args(annotation) else annotation


def _subscription_param_problem(parameters: list[inspect.Parameter]) -> str | None:
    # `inject_args` also loads a list or union of models, but a form field offers exactly one subscription.
    offending = [
        param.name
        for param in parameters
        if not _is_subscription_model(_without_optional(param.annotation))
        and any(_is_subscription_model(arg) for arg in get_args(param.annotation))
    ]
    return f"parameter(s) {', '.join(offending)} take a list or union of subscriptions" if offending else None


def describe_step(
    step_id: str, step: Step, product_tags_by_name: dict[str, str], used_in: list[str] | None = None
) -> StepInfo:
    func = orig(step)
    parameters = list(inspect.signature(func).parameters.values())
    sources = _annotation_source(func)

    def input_for(param: inspect.Parameter) -> StepInput:
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else Any
        has_default = param.default is not inspect.Parameter.empty
        source: InputSource = "state"
        if param.name == "state":
            source = "whole_state"
        elif _is_subscription_model(_without_optional(annotation)):
            source = "subscription_model"
        return StepInput(
            name=param.name,
            type=type_ref_for(annotation, sources.get(param.name), param.name, product_tags_by_name),
            annotation=_annotation_label(param.annotation, sources.get(param.name)),
            required=not has_default,
            default=_json_default(param.default) if has_default else None,
            source=source,
        )

    inputs = [input_for(param) for param in parameters if param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)]
    inference = infer_outputs(func, {step_input.name: step_input.type for step_input in inputs})
    model_params = {step_input.name for step_input in inputs if step_input.source == "subscription_model"}
    reason = _unusable_reason(step, parameters) or _subscription_param_problem(parameters)
    module, _, attribute = step_id.partition(":")
    doc = inspect.getdoc(func) or ""

    return StepInfo(
        id=step_id,
        name=step.name,
        function=attribute,
        module=module,
        category=_category(module),
        description=doc.split("\n\n")[0].strip(),
        kind=step_kind(step),
        inputs=inputs,
        outputs=inference.outputs,
        outputs_known=inference.known,
        usable=reason is None,
        unusable_reason=reason,
        # Returning a model makes `inject_args` save it, so such a step writes to the subscription.
        writes_subscription=any(output.key in model_params for output in inference.outputs),
        uses_subscription_models=bool(model_params),
        used_in_workflows=used_in or [],
    )


def _json_default(value: Any) -> Any:
    return value if isinstance(value, (str, int, float, bool, type(None), list, dict)) else repr(value)


def _category(module: str) -> str:
    """A short grouping for the palette: the sub package below a step package, e.g. `l2vpn` for `<pkg>.l2vpn.create`."""
    packages = sorted(app_settings.WORKFLOW_DESIGNER_STEP_PACKAGES, key=len, reverse=True)
    package = next((pkg for pkg in packages if module.startswith(f"{pkg}.")), None)
    if package is None:
        return module.split(".")[0]
    parts = module.removeprefix(f"{package}.").split(".")
    # A module directly in a step package (e.g. `modify_note`) has no sub package to group it by.
    return parts[0] if len(parts) > 1 else "general"


def is_step(value: Any) -> bool:
    """Whether `value` is a step function.

    Not `isinstance(value, Step)`: on Python 3.11 that protocol check calls `getattr` on every module attribute, and
    some, like the lazily configured `db`, raise for attributes they do not have.
    """
    return inspect.isfunction(value) and isinstance(getattr(value, "name", None), str) and hasattr(value, "form")


def _step_ids(modules: list[ModuleType]) -> dict[int, str]:
    """Map each Step object to its id, preferring the module that defines the function over re-exports."""
    candidates = [
        (module.__name__, attribute, value)
        for module in modules
        for attribute, value in vars(module).items()
        if is_step(value)
    ]
    ids: dict[int, str] = {}
    # Defining modules first, so a later re-export does not claim the id; setdefault keeps the first claim.
    for module_name, attribute, value in sorted(
        candidates, key=lambda item: (orig(item[2]).__module__ != item[0], item[0], item[1])
    ):
        ids.setdefault(id(value), f"{module_name}:{attribute}")
    return ids


def _workflow_usage() -> dict[int, list[str]]:
    usage: dict[int, list[str]] = {}
    for name, lazy_workflow in ALL_WORKFLOWS.items():
        try:
            workflow = lazy_workflow.instantiate()
        except Exception as exc:  # One broken workflow should not hide usage of all others.
            logger.warning("Could not instantiate workflow for step usage", workflow=name, error=str(exc))
        else:
            for step in workflow.steps:
                usage.setdefault(id(step), []).append(name)
    return usage


def product_tags_by_name() -> dict[str, str]:
    """Product name to tag, used to restrict which subscriptions a domain model parameter accepts."""
    try:
        with db.database_scope(), transactional(db, logger):
            rows = db.session.execute(select(ProductTable.name, ProductTable.tag)).all()
    except Exception as exc:  # Without the DB, subscription inputs lose their product restriction but still work.
        logger.warning("Could not read product tags for step discovery", error=str(exc))
        return {}
    return dict(rows)  # type: ignore[arg-type]


_cache: dict[str, StepInfo] | None = None
_objects: dict[str, Step] = {}
_lock = threading.Lock()


def register_step_package(package: str) -> None:
    """Offer the steps of `package` (e.g. an application's workflows package) in the workflow designer."""
    global _cache
    if package not in app_settings.WORKFLOW_DESIGNER_STEP_PACKAGES:
        app_settings.WORKFLOW_DESIGNER_STEP_PACKAGES.append(package)
        with _lock:
            _cache = None


def discover_steps(
    rescan: bool = False, product_tags: Callable[[], dict[str, str]] = product_tags_by_name
) -> dict[str, StepInfo]:
    """All steps defined in the configured packages, keyed by id. Importing every workflow module takes seconds."""
    global _cache
    with _lock:
        if _cache is not None and not rescan:
            return _cache

        started = time.monotonic()
        modules = iter_modules(app_settings.WORKFLOW_DESIGNER_STEP_PACKAGES)
        ids = _step_ids(modules)
        steps_by_id = {
            step_id: step
            for module in modules
            for step in vars(module).values()
            if is_step(step) and (step_id := ids.get(id(step)))
        }
        usage = _workflow_usage()
        tags = product_tags()
        infos = {}
        # An explicit loop because each step is described inside its own try/except.
        for step_id, step in steps_by_id.items():
            try:
                info = describe_step(step_id, step, tags, sorted(set(usage.get(id(step), []))))
            except Exception as exc:  # A step we cannot describe is left out rather than failing the whole scan.
                logger.warning("Could not describe step", step_id=step_id, error=str(exc))
            else:
                infos[step_id] = info
        _objects.clear()
        _objects.update(steps_by_id)
        _cache = dict(sorted(infos.items()))
        logger.info("Discovered workflow steps", steps=len(_cache), seconds=round(time.monotonic() - started, 1))
        return _cache


def resolve_step(step_id: str) -> Step | None:
    """Find a step by id without scanning; used when building a workflow, which must stay cheap."""
    if step_id in _objects:
        return _objects[step_id]
    module_name, _, attribute = step_id.partition(":")
    try:
        value = getattr(importlib.import_module(module_name), attribute)
    except (ImportError, AttributeError, ValueError):
        return None
    return value if is_step(value) else None
