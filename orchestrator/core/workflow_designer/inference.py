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

"""Infer which keys a step function adds to the workflow state, by reading the dict literals it returns.

Return annotations are always `State` (a plain dict), so the keys only exist in the function body. Only returns of
the step function itself count: nested functions and lambdas return to their caller, not to the engine.
"""

import ast
import builtins
import inspect
import textwrap
from collections.abc import Callable, Iterator
from functools import reduce
from typing import Any

import structlog
from pydantic import BaseModel

from orchestrator.core.workflow_designer.type_refs import ANY, TypeRef, type_ref_for

logger = structlog.get_logger(__name__)

_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
_CONSTANT_KINDS = {str: "str", int: "int", float: "float", bool: "bool"}


class StateKey(BaseModel):
    key: str
    type: TypeRef = ANY
    guaranteed: bool = True


class OutputInference(BaseModel):
    outputs: list[StateKey] = []
    # False when at least one return path adds keys that cannot be read from the source.
    known: bool = True


def _own_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Walk a function body without descending into nested scopes."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _SCOPE_NODES):
            continue
        yield child
        yield from _own_nodes(child)


def _always_exits(statements: list[ast.stmt]) -> bool:
    """Whether control can never fall off the end of `statements` (which would make the step return None)."""
    if not statements:
        return False
    last = statements[-1]
    match last:
        case ast.Return() | ast.Raise():
            return True
        case ast.If():
            return _always_exits(last.body) and _always_exits(last.orelse)
        case ast.With() | ast.AsyncWith():
            return _always_exits(last.body)
        case ast.Try():
            if _always_exits(last.finalbody):
                return True
            body_exits = _always_exits(last.orelse) if last.orelse else _always_exits(last.body)
            return body_exits and all(_always_exits(handler.body) for handler in last.handlers)
        case ast.Match():
            irrefutable = any(
                isinstance(case.pattern, ast.MatchAs) and case.pattern.pattern is None for case in last.cases
            )
            return irrefutable and all(_always_exits(case.body) for case in last.cases)
    return False


class _ValueTyper:
    """Guess the TypeRef of an expression that is stored under a state key."""

    def __init__(self, func: Callable, tree: ast.FunctionDef | ast.AsyncFunctionDef, params: dict[str, TypeRef]):
        self.func = func
        self.params = params
        self.namespace = {**vars(builtins), **getattr(func, "__globals__", {})}
        # Only a name bound exactly once has a single well defined value to look at.
        bindings: dict[str, list[ast.AST]] = {}
        for node in _own_nodes(tree):
            match node:
                case ast.Assign(targets=[ast.Name(id=name)], value=value):
                    bindings.setdefault(name, []).append(value)
                case ast.AnnAssign(target=ast.Name(id=name), annotation=annotation):
                    bindings.setdefault(name, []).append(ast.Subscript(value=annotation, slice=ast.Constant(None)))
                case ast.Assign() | ast.AugAssign() | ast.For() | ast.With() | ast.NamedExpr():
                    for target in ast.walk(node):
                        if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store):
                            bindings.setdefault(target.id, []).extend([ast.Constant(...), ast.Constant(...)])
        self.bindings = {name: values[0] for name, values in bindings.items() if len(values) == 1}

    def _evaluate(self, node: ast.expr) -> Any:
        # Only names and dotted attributes; anything that would run code is refused by the node filter.
        if not all(isinstance(child, (ast.Name, ast.Attribute, ast.Load)) for child in ast.walk(node)):
            return None
        try:
            return eval(compile(ast.Expression(body=node), "<annotation>", "eval"), self.namespace)  # noqa: S307
        except Exception:
            return None

    def _annotation(self, node: ast.expr) -> TypeRef:
        try:
            annotation = eval(compile(ast.Expression(body=node), "<annotation>", "eval"), self.namespace)  # noqa: S307
        except Exception:
            return ANY
        return type_ref_for(annotation, ast.unparse(node))

    def _call(self, node: ast.Call) -> TypeRef:
        callee = self._evaluate(node.func)
        if callee is None:
            return ANY
        if isinstance(callee, type):
            return type_ref_for(callee)
        try:
            signature = inspect.signature(callee)
        except (TypeError, ValueError):
            return ANY
        if signature.return_annotation is inspect.Signature.empty:
            return ANY
        return type_ref_for(signature.return_annotation)

    def type_of(self, node: ast.expr, depth: int = 0) -> TypeRef:
        match node:
            case ast.Constant(value=None):
                return TypeRef(optional=True)
            case ast.Constant(value=value) if type(value) in _CONSTANT_KINDS:
                return TypeRef(kind=_CONSTANT_KINDS[type(value)])  # type: ignore[arg-type]
            case ast.JoinedStr():
                return TypeRef(kind="str")
            case ast.Compare() | ast.UnaryOp(op=ast.Not()) | ast.BoolOp(values=[ast.Compare(), *_]):
                return TypeRef(kind="bool")
            case ast.List() | ast.ListComp() | ast.Set() | ast.SetComp() | ast.Tuple() | ast.GeneratorExp():
                return TypeRef(kind="list")
            case ast.Dict() | ast.DictComp():
                return TypeRef(kind="dict")
            case ast.Call():
                return self._call(node)
            case ast.Name(id=name):
                return self._name(name, depth)
        return ANY

    def _name(self, name: str, depth: int) -> TypeRef:
        if name in self.params:
            return self.params[name]
        if name not in self.bindings or depth >= 3:
            return ANY
        bound = self.bindings[name]
        # An annotated local was stored as `<annotation>[None]`, see __init__.
        if isinstance(bound, ast.Subscript) and isinstance(bound.slice, ast.Constant) and bound.slice.value is None:
            return self._annotation(bound.value)
        return self.type_of(bound, depth + 1)  # type: ignore[arg-type]


def _merge_types(types: list[TypeRef]) -> TypeRef:
    first = types[0]
    same_kind = all(ref.kind == first.kind and ref.model == first.model for ref in types)
    return first.model_copy(update={"optional": any(ref.optional for ref in types)}) if same_kind else ANY


def _parse_function(func: Callable) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    try:
        source = textwrap.dedent(inspect.getsource(func))
        module = ast.parse(source)
    except (OSError, TypeError, SyntaxError):
        return None
    return next(
        (node for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))),
        None,
    )


def infer_outputs(func: Callable, params: dict[str, TypeRef]) -> OutputInference:
    """Infer the state keys `func` returns; `params` are the TypeRefs of its parameters, for pass-through values."""
    tree = _parse_function(func)
    if tree is None:
        return OutputInference(known=False)

    typer = _ValueTyper(func, tree, params)
    returns = [node for node in _own_nodes(tree) if isinstance(node, ast.Return)]
    paths: list[dict[str, TypeRef]] = [] if _always_exits(tree.body) else [{}]
    known = True
    for node in returns:
        match node.value:
            case None | ast.Constant(value=None):
                paths.append({})
            case ast.Dict(keys=keys, values=values) if all(
                isinstance(key, ast.Constant) and isinstance(key.value, str) for key in keys
            ):
                paths.append(
                    {
                        key.value: typer.type_of(value)  # type: ignore[union-attr]
                        for key, value in zip(keys, values, strict=True)
                        if not key.value.startswith("__")  # type: ignore[union-attr]
                    }
                )
            case ast.Dict(keys=keys, values=values):
                # A `**spread` adds keys we cannot see; the literal keys next to it are still returned.
                known = False
                paths.append(
                    {
                        key.value: typer.type_of(value)
                        for key, value in zip(keys, values, strict=True)
                        if isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and not key.value.startswith("__")
                    }
                )
            case _:
                known = False

    if not paths:
        return OutputInference(known=known)

    guaranteed = reduce(set.intersection, (set(path) for path in paths))
    all_keys = list(dict.fromkeys(key for path in paths for key in path))
    outputs = [
        StateKey(
            key=key,
            type=_merge_types([path[key] for path in paths if key in path]),
            guaranteed=key in guaranteed,
        )
        for key in all_keys
    ]
    return OutputInference(outputs=outputs, known=known)
