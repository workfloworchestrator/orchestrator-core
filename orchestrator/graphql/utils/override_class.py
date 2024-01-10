from typing import Any


def override_class(strawberry_class: Any, fields: dict) -> Any:
    """Override fields or add fields to a existing strawberry class.

    Usefull for overriding orchestrator core strawberry classes.

    Parameters:
        - strawberry_class: The strawberry class which you want to change fields.
        - fields: a dict with strawberry fields to override or add to the strawberry class.

    returns the strawberry class with changed fields.
    """

    if not fields:
        return strawberry_class

    def override_fn(field: Any) -> Any:
        if custom_field := fields.get(field.name):
            field.base_resolver = custom_field.base_resolver
            return field
        return field

    default_class_field_names = [field.name for field in strawberry_class.__strawberry_definition__._fields]

    new_field_list = [override_fn(field) for field in strawberry_class.__strawberry_definition__._fields]
    new_field_list.extend([field for field in fields.values() if field.name not in default_class_field_names])

    strawberry_class.__strawberry_definition__._fields = new_field_list
    return strawberry_class
