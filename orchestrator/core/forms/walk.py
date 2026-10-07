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

"""A walk of a form that ends in a page model, not a rendered schema.

pydantic-forms' ``post_form`` hands out the next page only as the JSON schema it renders for the browser
(inside ``FormNotCompleteError``) and raises ``FormValidationError`` without saying which page failed. The
agent-facing form tool needs the page's model class, to describe its fields as data, and the index of a
rejected page. ``walk_form`` is ``post_form``'s loop with those outcomes as values; the validation and its
translated messages are the same, so a rejection reads exactly as it does in the UI.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from pydantic import ValidationError
from pydantic_i18n import PydanticI18n

from pydantic_forms.core.translations import translations
from pydantic_forms.exceptions import FormOverflowError, FormValidationError
from pydantic_forms.types import InputForm, State, StateInputFormGenerator


@dataclass(frozen=True)
class NextPage:
    """The form asks for another page: its model, and its index (the number of pages accepted before it)."""

    model: InputForm
    index: int


@dataclass(frozen=True)
class Complete:
    """Every page was accepted: the form's result, what ``post_form`` returns."""

    state: State


@dataclass(frozen=True)
class Rejected:
    """A page did not validate: which one, its model, and the verdict as the UI would show it."""

    model: InputForm
    index: int
    error: FormValidationError


def walk_form(
    form_generator: StateInputFormGenerator | None,
    state: State,
    user_inputs: list[State],
    locale: str = "en_US",
) -> NextPage | Complete | Rejected:
    """Feed ``user_inputs`` to the form page by page, as ``post_form`` does, and say where that ends.

    Raises:
        FormOverflowError: more inputs than the form has pages.
    """
    if form_generator is None:
        return Complete({})
    current_state = deepcopy(state)
    generator = form_generator(current_state)
    pending = list(user_inputs)
    try:
        page = generator.send(None)  # the priming send, as post_form does
        while pending:
            user_input = pending.pop(0)
            try:
                validated = page(**user_input)
            except ValidationError as exc:
                verdict = FormValidationError(page.__name__, exc, PydanticI18n(translations), locale)
                return Rejected(page, len(user_inputs) - len(pending) - 1, verdict)
            current_state.update(validated.model_dump())
            page = generator.send(validated)
    except StopIteration as done:
        if pending:
            raise FormOverflowError(f"Did not process all user_inputs ({len(pending)} remaining)") from None
        return Complete(done.value)
    return NextPage(page, len(user_inputs))
