# Copyright 2019-2020 SURF.
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


from copy import deepcopy
from typing import Any, Dict, Generator, List, Optional, TypedDict, Union, cast

import structlog
from pydantic.error_wrappers import ValidationError, display_errors
from pydantic.fields import Field, ModelField, Undefined
from pydantic.main import BaseModel, Extra  # type: ignore

from orchestrator.types import JSON, InputForm, State, StateInputFormGenerator
from orchestrator.utils.json import json_dumps, json_loads

logger = structlog.get_logger(__name__)


__all__ = ("generate_form", "post_process", "FormNotCompleteError", "FormValidationError", "FormException")


class FormException(Exception):
    pass


class FormNotCompleteError(FormException):
    form: InputForm

    def __init__(self, form: JSON):
        super().__init__(form)
        self.form = form


class PydanticErrorDict(TypedDict):
    loc: List[Union[str, int]]
    type: str
    msg: str
    ctx: Dict[str, Any]


class FormValidationError(FormException):
    validator_name: str
    errors: List[PydanticErrorDict]

    def __init__(self, validator_name: str, errors: List[Dict[str, Any]]):
        super().__init__(validator_name, errors)
        self.validator_name = validator_name
        self.errors = cast(List[PydanticErrorDict], errors)

    def __str__(self) -> str:
        no_errors = len(self.errors)
        return (
            f'{no_errors} validation error{"" if no_errors == 1 else "s"} for {self.validator_name}\n'
            f"{display_errors(cast(List[Dict[str, Any]], self.errors))}"  # type: ignore
        )


def generate_form(
    form_generator: Optional[StateInputFormGenerator], state: State, user_inputs: List[State]
) -> Optional[InputForm]:
    """Generate form using form generator as defined by a workflow."""
    try:
        # Generate form is basically post_process
        post_process(form_generator, state, user_inputs)
    except FormNotCompleteError as e:
        # Form is not finished and raises the next form, this is expected
        return e.form

    # Form is finished and thus there is no new form
    return None


def post_process(form_generator: Optional[StateInputFormGenerator], state: State, user_inputs: List[State]) -> State:
    """Post process user_input based on form definition from workflow."""

    # there is no form_generator so we return no validated data
    if not form_generator:
        return {}

    current_state = deepcopy(state)

    logger.debug("Post process form", state=state, user_inputs=user_inputs)

    # Generate generator
    generator = form_generator(current_state)

    try:
        # Generate first form (we need to send None here, since the arguments are already given when we generated the generator)
        generated_form: InputForm = generator.send(None)

        # Loop through user inputs and for each input validate and update current state and validation results
        for user_input in user_inputs:
            # Validate
            try:
                form_validated_data = generated_form(**user_input)
            except ValidationError as e:
                raise FormValidationError(e.model.__name__, e.errors()) from e  # type: ignore

            # Update state with validated_data
            current_state.update(form_validated_data.dict())

            # Make next form
            generated_form = generator.send(form_validated_data)

        else:
            # Form is not completely filled raise next form
            raise FormNotCompleteError(generated_form.schema())
    except StopIteration as e:
        # Form is completely filled so we can return the last of the data and
        return e.value


class DisplayOnlyFieldType:
    @classmethod
    def __get_validators__(cls) -> Generator:
        yield cls.nothing

    def nothing(cls, v: Any, field: ModelField) -> Any:
        return field.default


class FormPage(BaseModel):
    class Config:
        json_loads = json_loads
        json_dumps = json_dumps
        title = "unknown"
        extra = Extra.forbid
        validate_all = True

    def __init_subclass__(cls, /, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)  # type:ignore

        # The default and requiredness of a field is not a property of a field
        # In the case of DisplayOnlyFieldTypes, we do kind of want that.
        # Using this method we set the right properties after the form is created
        for field in cls.__fields__.values():
            try:
                if issubclass(field.type_, DisplayOnlyFieldType):
                    field.required = False
                    field.allow_none = True
            except TypeError:
                pass


def ReadOnlyField(
    default: Any = Undefined,
    *,
    const: Optional[bool] = None,
    **extra: Any,
) -> Any:
    return Field(default, const=True, uniforms={"disabled": True, "value": default}, **extra)
