from typing import Any, TypeVar, cast

T = TypeVar("T")


def get_original_model(model: Any, klass: T) -> T:
    """Get original type in a typesafe way."""
    original_model = getattr(model, "_original_model", None)

    if original_model:
        return cast(T, original_model)
    raise ValueError(f"Cant get original model for type {klass}")
