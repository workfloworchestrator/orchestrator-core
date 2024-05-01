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

import inspect
import types
from collections.abc import Callable, Iterable, Sequence
from enum import IntEnum, StrEnum
from functools import partial
from typing import get_args, get_origin

import strawberry
from more_itertools import consume, first_true, side_effect
from pydantic import create_model
from pydantic.fields import FieldInfo
from strawberry.experimental.pydantic.conversion_types import StrawberryTypeFromPydantic

from nwastdlib import const
from orchestrator.domain.base import DomainModel
from orchestrator.types import is_list_type
from pydantic_forms.types import strEnum

MatchFunc = Callable
ActionFunc = Callable
ModifyMap = Iterable[tuple[MatchFunc, ActionFunc]]


def is_subclass_of(annotation: type, class_or_tuple: type | tuple[type]) -> bool:
    return inspect.isclass(annotation) and issubclass(annotation, class_or_tuple)


is_domain_model = partial(is_subclass_of, class_or_tuple=DomainModel)
is_int_enum = partial(is_subclass_of, class_or_tuple=IntEnum)
is_str_enum = partial(is_subclass_of, class_or_tuple=(strEnum, StrEnum))


def is_optional_enum_of_type(annotation: type | None, is_type_enum: Callable) -> bool:
    origin = get_origin(annotation)
    if origin is not None and origin is types.UnionType:
        args = get_args(annotation)
        return len(args) == 2 and is_type_enum(args[0]) and args[1] is type(None)
    return False


is_optional_int_enum = partial(is_optional_enum_of_type, is_type_enum=is_int_enum)
is_optional_str_enum = partial(is_optional_enum_of_type, is_type_enum=is_str_enum)


def map_type(annotation: type | None, modify_map: ModifyMap) -> type | None:
    match first_true(modify_map, pred=lambda match: match[0](annotation)):
        case _, action:
            return action(annotation, modify_map)
        case _:
            return None


def class_walker(klass: type[DomainModel], modify_map: ModifyMap) -> type[DomainModel]:
    def map_field(fi: FieldInfo) -> None:
        annotation = fi.annotation
        if mapped_type := map_type(annotation, modify_map):
            fi.annotation = mapped_type
        if is_list_type(annotation):
            orig_type = get_args(annotation)[0]
            if mapped_type := map_type(orig_type, modify_map):
                fi.annotation = list[mapped_type]  # type: ignore

    clone = create_model(f"{klass.__name__}_CLONE", __base__=klass)
    fields = clone.model_fields.values()
    consume(side_effect(map_field, fields))

    return clone


MODIFY_MAP = (
    (is_domain_model, class_walker),
    (is_str_enum, const(str)),
    (is_int_enum, const(int)),
    (is_optional_str_enum, const(str | None)),
    (is_optional_int_enum, const(int | None)),
)


def modify_class(klass: type[DomainModel]) -> type[DomainModel]:
    return class_walker(klass, modify_map=MODIFY_MAP)


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
    mapper_func = strawberry.experimental.pydantic.type(
        updated_model,
        name=name,
        all_fields=all_fields,
        directives=directives,
        description=description,
        use_pydantic_alias=use_pydantic_alias,
    )

    def updated_mapper_func(*args, **kwargs):
        map_result = mapper_func(*args, **kwargs)
        # NOTE: dirty hack to register the intermediate type as a strawberry type
        model._strawberry_type = updated_model._strawberry_type
        return map_result

    return updated_mapper_func
