import contextlib
from collections.abc import Iterable, Iterator
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from orchestrator.db import ProductBlockTable, SubscriptionInstanceTable, db
from orchestrator.types import filter_nonetype, get_origin_and_args, is_union_type
from orchestrator.utils.functional import group_by_key
from pydantic_forms.types import UUIDstr


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


@contextlib.contextmanager
def no_private_attrs(model: Any) -> Iterator:
    """PrivateAttrs from the given pydantic BaseModel are removed for the duration of this context."""
    if not isinstance(model, BaseModel):
        yield
        return
    private_attrs_reference = model.__pydantic_private__
    try:
        model.__pydantic_private__ = {}
        yield
    finally:
        model.__pydantic_private__ = private_attrs_reference


def get_root_blocks_to_instance_ids(subscription_id: UUID | UUIDstr) -> dict[str, list[UUID]]:
    """Returns mapping of root product block names to list of subscription instance ids.

    While recommended practice is to have only 1 root product block, it is possible to have multiple blocks or even a
    list of root blocks. This function supports that.
    """
    block_name_to_instance_id_rows = db.session.execute(
        select(ProductBlockTable.name, SubscriptionInstanceTable.subscription_instance_id)
        .select_from(SubscriptionInstanceTable)
        .join(ProductBlockTable)
        .where(SubscriptionInstanceTable.subscription_id == subscription_id)
        .order_by(ProductBlockTable.name)
    ).all()

    return group_by_key(block_name_to_instance_id_rows)  # type: ignore[arg-type]
