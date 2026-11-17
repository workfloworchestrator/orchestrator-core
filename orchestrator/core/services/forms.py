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
"""A workflow's form as the agent tools read it: the walk, and the options of a field that says where they are fetched (pydantic-forms' ``optionsSource``).

A browser follows the source itself. A caller of the agent tools cannot, so the form tools read it here: a
short list is written into the page schema as a choice, a long one is found with the options tool, and a
submitted value is checked against the list.
"""

import copy
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from http import HTTPStatus
from typing import Any, NamedTuple
from urllib.parse import quote, urlsplit

import httpx
import structlog
from fastapi import Request
from starlette.concurrency import run_in_threadpool

from orchestrator.core.workflow import Workflow
from pydantic_forms.core import FormFieldError, NextPage, WalkOutcome, page_schema, walk_form
from pydantic_forms.utils.pointer import parse_pointer, unescape
from pydantic_forms.utils.schema import DEPENDS_ON, OPTIONS_SOURCE, nodes_with

logger = structlog.get_logger(__name__)

MAX_INLINE = 10  # a list of at most this many options is written into the page schema

Fetch = Callable[[str], Awaitable[Any]]  # GET the JSON document at a source's URL, as the caller


def own_api(request: Request) -> Fetch:
    """GET a JSON document from a route of this API, in process and as the caller: where a field's options are."""
    authorization = request.headers.get("authorization")
    headers = {"authorization": authorization} if authorization else {}

    async def fetch(url: str) -> Any:
        if urlsplit(url).netloc:
            raise ValueError(f"{url} is not a route of this API")
        transport = httpx.ASGITransport(app=request.app)
        async with httpx.AsyncClient(transport=transport, base_url=str(request.base_url), headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    return fetch


async def walk(wf: Workflow, workflow_key: str, user_inputs: list[dict[str, Any]]) -> WalkOutcome:
    """Walk the workflow's form with the pages filled so far: what comes after them."""
    initial_state: dict[str, Any] = {"workflow_name": workflow_key, "workflow_target": wf.target}
    # Form generators use the sync database session, so the walk runs off the event loop.
    return await run_in_threadpool(walk_form, wf.initial_input_form, initial_state, user_inputs)


async def judge_submitted(
    wf: Workflow, workflow_key: str, user_inputs: list[dict[str, Any]], fetch: Fetch
) -> tuple[NextPage | None, list[FormFieldError], dict[str, Any]]:
    """The page just submitted, checked against its option sources: the form takes any string for a sourced field.

    Returns that page, the values no source offers, and how the offered ones are shown; no page when there is
    nothing to check.
    """
    if not user_inputs:
        return None, [], {}
    before = await walk(wf, workflow_key, user_inputs[:-1])
    if not isinstance(before, NextPage):
        return None, [], {}
    strangers, labels = await judge(page_schema(before.model, inline_refs=True), user_inputs[-1], fetch)
    return before, strangers, labels


class Option(NamedTuple):
    value: str | int
    label: str


def sourced_fields(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The page's fields that have an options source, each with the schema node that carries it.

    The node is the property itself, the items of a list, or the non-null branch of a nullable field.
    """
    fields: dict[str, dict[str, Any]] = {}
    for node in nodes_with(schema, OPTIONS_SOURCE):
        match node.location.split("/"):
            case ["", "properties", name, *rest] if "properties" not in rest:
                fields.setdefault(unescape(name), node.schema)
    return fields


async def options_of(
    source: Mapping[str, Any], values: Mapping[str, Any], fetch: Fetch, search: str | None = None, whole: int = 0
) -> list[Option] | None:
    """The options a source gives; None while a value its URL needs is missing.

    A list of at most ``whole`` options is given as it is, for the caller to pick from. A longer one is
    narrowed by ``search``: by the server when the source declares a ``search`` parameter, which a long list
    should, else to the options that contain it.
    """
    if (url := _filled(source["url"], source, values)) is None:
        return None
    if search and (param := source.get("search")):
        return _options_in(source, await fetch(f"{url}{'&' if '?' in url else '?'}{quote(param)}={quote(search)}"))
    options = _options_in(source, await fetch(url))
    return _narrow(options, search) if search and len(options) > whole else options


async def write_options(schema: Mapping[str, Any], values: Mapping[str, Any], fetch: Fetch) -> dict[str, Any]:
    """``schema`` with each short sourced list written in as a choice (``enum`` and ``options``).

    A longer list, one that waits for another value of the page, or one that cannot be read keeps its
    ``optionsSource``: its options are found with the options tool. So does a source that searches on its
    server, which may give only part of its list without a term.
    """
    written = copy.deepcopy(dict(schema))
    for name, node in sourced_fields(written).items():
        if node[OPTIONS_SOURCE].get("search"):
            continue
        try:
            options = await options_of(node[OPTIONS_SOURCE], values, fetch)
        except Exception as exc:
            logger.warning("A form field's options could not be read", field=name, error=str(exc))
            continue
        if options and len(options) <= MAX_INLINE:
            del node[OPTIONS_SOURCE]
            node["enum"] = [option.value for option in options]
            node["options"] = {str(option.value): option.label for option in options}
    return written


async def judge(
    schema: dict[str, Any], submitted: Mapping[str, Any], fetch: Fetch
) -> tuple[list[FormFieldError], dict[str, Any]]:
    """Whether each sourced field's submitted value is one of its options, and how those values are shown.

    The form takes any string for such a field, so a value nobody was offered is caught here. A field whose
    options cannot be read is not judged. Neither is a value that a source which searches on its server does
    not list, unless the source declares a ``lookup``: its whole list cannot be seen from here.
    """
    errors: list[FormFieldError] = []
    labels: dict[str, Any] = {}
    for name, node in sourced_fields(schema).items():
        if (value := submitted.get(name)) in (None, "", []):
            continue
        source = node[OPTIONS_SOURCE]
        items = value if isinstance(value, list) else [value]
        try:
            known = await _labels_of(source, submitted, items, fetch)
        except Exception as exc:
            logger.warning("A form field's options could not be read", field=name, error=str(exc))
            continue
        if known is None:
            continue
        strangers = [item for item in items if str(item) not in known]
        if strangers and (source.get("lookup") or not source.get("search")):
            msg = f"{strangers!r} is not among the field's options: find the value with get_workflow_form_options"
            errors.append(FormFieldError(loc=[name], msg=msg, type="value_error"))
        elif not strangers:
            shown = [known[str(item)] for item in items]
            labels[name] = shown if isinstance(value, list) else shown[0]
    return errors, labels


async def _labels_of(
    source: Mapping[str, Any], values: Mapping[str, Any], items: Sequence[Any], fetch: Fetch
) -> dict[str, str] | None:
    """The labels of ``items`` that are options of the source, by value; None while a value its URL needs is missing.

    A source that declares ``lookup`` is asked for each item by itself. Any other is read as a list, which
    is whole unless the source searches on its server.
    """
    if (lookup := source.get("lookup")) is None:
        options = await options_of(source, values, fetch)
        return None if options is None else {str(option.value): option.label for option in options}
    known: dict[str, str] = {}
    for item in items:
        if (url := _filled(lookup, source, values, value=item)) is None:
            return None
        try:
            known[str(item)] = _option(source, await fetch(url)).label
        except httpx.HTTPStatusError as error:
            if error.response.status_code != HTTPStatus.NOT_FOUND:
                raise
    return known


def _filled(template: str, source: Mapping[str, Any], values: Mapping[str, Any], **more: Any) -> str | None:
    """A URL of the source with its placeholders filled from the page's values; None while one has no value yet."""
    pointers: Mapping[str, str] = source.get(DEPENDS_ON) or {}
    found = {name: _value_at(values, pointer) for name, pointer in pointers.items()} | more
    if any(value in (None, "", []) for value in found.values()):
        return None
    # A value goes into the URL as a browser writes it: a string as it is, anything else as JSON (true, 10000).
    texts = {name: value if isinstance(value, str) else json.dumps(value) for name, value in found.items()}
    if dots := [text for text in texts.values() if text in (".", "..")]:
        raise ValueError(f"{dots[0]!r} would change the path of {template}")
    return str(template).format_map({name: quote(text, safe="") for name, text in texts.items()})


def _value_at(values: Mapping[str, Any], pointer: str) -> Any:
    """The page value a ``dependsOn`` pointer names: from the page (``/name``) or beside the field (``1/name``)."""
    parsed = parse_pointer(pointer)
    if parsed is None or parsed.levels_up not in (None, 1):
        return None
    node: Any = values
    for segment in parsed.segments:
        if isinstance(node, Mapping):
            node = node.get(segment)
        elif isinstance(node, list) and segment.isdigit() and int(segment) < len(node):
            node = node[int(segment)]
        else:
            return None
    return node


def _options_in(source: Mapping[str, Any], document: Any) -> list[Option]:
    """The options a response holds: the list at ``items`` (or the response itself), each row as the source reads it."""
    rows = document
    if (pointer := source.get("items")) is not None:
        rows = _value_at(document, pointer) if isinstance(document, Mapping) else None
    if not isinstance(rows, list):
        raise ValueError(f"the response of {source['url']} holds no list where the source expects one")
    return [_option(source, row) for row in rows]


def _option(source: Mapping[str, Any], row: Any) -> Option:
    value_key, label = source.get("value"), source.get("label")
    value = row if value_key is None else row[value_key]
    if label is None:
        shown = str(value)
    elif "{" in label:
        shown = label.format_map(row)
    else:
        shown = str(row[label])
    return Option(value if isinstance(value, (str, int)) and not isinstance(value, bool) else str(value), shown)


def _narrow(options: Sequence[Option], search: str) -> list[Option]:
    """The options whose label or value contains ``search``, as a browser's pick list filters: a fallback for a long list whose source declares no ``search`` parameter."""
    needle = search.strip().casefold()
    return [o for o in options if needle in o.label.casefold() or needle in str(o.value).casefold()]
