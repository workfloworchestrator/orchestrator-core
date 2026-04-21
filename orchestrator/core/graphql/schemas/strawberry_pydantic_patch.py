from typing import Any, cast

import strawberry
from strawberry.experimental.pydantic.conversion import _convert_from_pydantic_to_strawberry_type
from strawberry.types.field import StrawberryField

# Vendored convert_pydantic_model_to_strawberry_class from
# https://github.com/strawberry-graphql/strawberry/blob/d721eb33176cfe22be5e47f5bf2c21a4a022a6d6/strawberry/experimental/pydantic/conversion.py
# And patched it so data loading happens inside the `if field init:`
# TODO: when confirmed to work without side-effects/regressions, create Issue/PR in strawberry-graphql


def convert_pydantic_model_to_strawberry_class__patched(
    cls: Any,  # noqa: ANN001
    *,
    model_instance: Any = None,  # noqa: ANN001
    extra: Any = None,  # noqa: ANN001
) -> Any:
    extra = extra or {}
    kwargs = {}

    for field_ in cls.__strawberry_definition__.fields:
        field = cast(StrawberryField, field_)
        python_name = field.python_name

        # only convert and add fields to kwargs if they are present in the `__init__`
        # method of the class
        if field.init:
            data_from_extra = extra.get(python_name, None)
            data_from_model = getattr(model_instance, python_name, None) if model_instance else None

            kwargs[python_name] = _convert_from_pydantic_to_strawberry_type(
                field.type, data_from_model, extra=data_from_extra
            )

    return cls(**kwargs)


strawberry.experimental.pydantic.object_type.convert_pydantic_model_to_strawberry_class = (  # type: ignore
    convert_pydantic_model_to_strawberry_class__patched
)
