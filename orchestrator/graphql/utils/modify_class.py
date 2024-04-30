# Copyright 2019-2023 SURF.
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

import copy
import inspect
import types
from collections.abc import Callable, Sequence
from enum import IntEnum, StrEnum
from functools import partial
from typing import get_args, get_origin, cast

import strawberry
from strawberry.experimental.pydantic.conversion_types import StrawberryTypeFromPydantic

from orchestrator.domain.base import DomainModel
from pydantic_forms.types import strEnum


def is_domain_model(annotation: type | None) -> bool:
    return inspect.isclass(annotation) and issubclass(annotation, DomainModel)


def is_int_enum(annotation: type | None) -> bool:
    return inspect.isclass(annotation) and issubclass(annotation, IntEnum)


def is_str_enum(annotation: type | None) -> bool:
    return inspect.isclass(annotation) and issubclass(annotation, (strEnum, StrEnum))


def is_optional_enum_of_type(annotation: type | None, is_type_enum: Callable) -> bool:
    origin = get_origin(annotation)
    if origin is not None and origin is types.UnionType:
        args = get_args(annotation)
        return len(args) == 2 and is_type_enum(args[0]) and args[1] is type(None)
    return False


is_optional_int_enum = partial(is_optional_enum_of_type, is_type_enum=is_int_enum)
is_optional_str_enum = partial(is_optional_enum_of_type, is_type_enum=is_str_enum)


def modify_class(klass: type[DomainModel]) -> type[DomainModel]:  # noqa: C901
    clone = copy.deepcopy(klass)

    # TODO: replace by a nice extendable tree-walker implementation with some match:action map

    for _key, fi in clone.model_fields.items():
        annotation = fi.annotation
        if is_domain_model(annotation):
            assert annotation  # make mypy happy
            fi.annotation = modify_class(annotation)
        if is_str_enum(annotation):
            fi.annotation = str
        if is_optional_str_enum(annotation):
            fi.annotation = str | None  # type: ignore
        if is_int_enum(annotation):
            fi.annotation = int
        if is_optional_int_enum(annotation):
            fi.annotation = int | None  # type: ignore
        if get_origin(annotation) is list:
            orig_type = get_args(annotation)[0]
            if is_domain_model(orig_type):
                fi.annotation = list[modify_class(orig_type)]  # type: ignore
            if is_str_enum(orig_type):
                fi.annotation = list[str]
            if is_optional_str_enum(orig_type):
                fi.annotation = list[str | None]
            if is_int_enum(orig_type):
                fi.annotation = list[int]
            if is_optional_int_enum(orig_type):
                fi.annotation = list[int | None]
    return clone


def strawberry_orchestrator_type(
    model: type,
    *,
    name: str | None = None,
    all_fields: bool = True,
    description: str | None = None,
    directives: Sequence[object] | None = (),
    use_pydantic_alias: bool = True,
) -> Callable[..., type[StrawberryTypeFromPydantic[DomainModel]]]:
    updated_model = modify_class(model)
    return strawberry.experimental.pydantic.type(
        updated_model,
        name=name,
        all_fields=all_fields,
        directives=directives,
        description=description,
        use_pydantic_alias=use_pydantic_alias,
    )
