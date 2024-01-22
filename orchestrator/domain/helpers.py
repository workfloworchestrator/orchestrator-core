from collections.abc import Iterable

from orchestrator.types import filter_nonetype, get_origin_and_args, is_union_type


def _to_product_block_field_type_iterable(product_block_field_type: type | tuple[type]) -> Iterable[type]:
    """Return an iterable of types in the given product block field.

    Notes:
        There is a type-checking pattern (if optional, if union, if list/tuple, etc) which occurs multiple times in
        base.py and other parts of the codebase. We should try to combine those into one function.
        However, this function works based on field types as returned by
        DomainModel._get_depends_on_product_block_types() so it is not directly applicable.
    """
    _origin, args = get_origin_and_args(product_block_field_type)

    if is_union_type(product_block_field_type):
        return list(filter_nonetype(args))

    if isinstance(product_block_field_type, tuple):
        return product_block_field_type

    return [product_block_field_type]
