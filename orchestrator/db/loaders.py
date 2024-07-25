from functools import reduce
from typing import Any, Callable, Iterator, NamedTuple, cast

import structlog
from sqlalchemy import inspect
from sqlalchemy.ext.associationproxy import ObjectAssociationProxyInstance
from sqlalchemy.orm import (
    InstrumentedAttribute,
    Load,
    RelationshipDirection,
    RelationshipProperty,
    joinedload,
    selectinload,
    subqueryload,
)
from sqlalchemy.orm.strategies import SubqueryLoader

from orchestrator.db import ALL_DB_MODELS
from orchestrator.db.database import BaseModel as DbBaseModel

logger = structlog.get_logger()

LoaderFunc = Callable[..., Load]


class AttrLoader(NamedTuple):
    loader_fn: LoaderFunc
    attr: InstrumentedAttribute
    next_model: type[DbBaseModel]


_MODEL_LOADERS: dict[type[DbBaseModel], dict[str, list[AttrLoader]]] = {}


def _relation_type_to_loader_func(relationship: RelationshipProperty) -> LoaderFunc:
    match relationship.direction:
        case RelationshipDirection.MANYTOONE:
            # Always eagerload this through a join
            return cast(LoaderFunc, joinedload)
        case RelationshipDirection.MANYTOMANY | RelationshipDirection.ONETOMANY:
            # Respect the strategy configured on the relationship
            loader_fn = subqueryload if isinstance(relationship.strategy, SubqueryLoader) else selectinload
            return cast(LoaderFunc, loader_fn)
    raise TypeError(f"Unrecognized relationship direction {relationship.direction}")


def _inspect_relationships(model: type[DbBaseModel]) -> Iterator[tuple[str, list[AttrLoader]]]:
    model_inspect: Any = inspect(model)

    def make_attr_loader(model: type[DbBaseModel], relation: RelationshipProperty) -> AttrLoader:
        loader = _relation_type_to_loader_func(relation)
        attr = cast(InstrumentedAttribute, getattr(model, relation.key))
        next_model = cast(type[DbBaseModel], relation.entity.entity)
        return AttrLoader(loader, attr, next_model)

    yield from ((relation.key, [make_attr_loader(model, relation)]) for relation in model_inspect.relationships)


def _inspect_assocation_proxies(first_model: type[DbBaseModel]) -> Iterator[tuple[str, list[AttrLoader]]]:

    # Association proxies are not inspectable so they require some extra work
    # https://github.com/sqlalchemy/sqlalchemy/discussions/10047
    # E.g. for the association_proxy ProductBlockTable.in_use_by we want to end up with the loader:
    #   selectinload(ProductBlockTable.in_use_by_block_relations).joinedload(ProductBlockRelationTable.in_use_by)
    def is_assoc_proxy(attr_name: str) -> bool:
        if attr_name.startswith("_"):
            return False
        attr = getattr(first_model, attr_name)
        return isinstance(attr, ObjectAssociationProxyInstance)

    assoc_proxy_attrs = (attr_name for attr_name in dir(first_model) if is_assoc_proxy(attr_name))

    def to_relation_names(attr_name: str) -> tuple[str, str]:
        attr: ObjectAssociationProxyInstance = getattr(first_model, attr_name)
        return attr.target_collection, attr.value_attr

    def make_attr_loader(model: type[DbBaseModel], relation_name: str) -> AttrLoader:
        inspected: Any = inspect(model)
        relation: RelationshipProperty = inspected.relationships[relation_name]
        loader = _relation_type_to_loader_func(relation)
        attr = cast(InstrumentedAttribute, getattr(model, relation_name))
        return AttrLoader(loader, attr, model)

    model_inspect: Any = inspect(first_model)
    for attr_name in assoc_proxy_attrs:
        first_relation_name, second_relation_name = to_relation_names(attr_name)
        first_attr_loader = make_attr_loader(first_model, first_relation_name)

        first_relation: RelationshipProperty = model_inspect.relationships[first_relation_name]
        second_model = cast(type[DbBaseModel], first_relation.entity.entity)
        second_attr_loader = make_attr_loader(second_model, second_relation_name)

        yield attr_name, [first_attr_loader, second_attr_loader]


def _inspect_model(model: type[DbBaseModel]) -> Iterator[tuple[str, list[AttrLoader]]]:
    yield from _inspect_relationships(model)
    yield from _inspect_assocation_proxies(model)


def init_model_loaders() -> None:
    """Inspects relationships from all SQLAlchemy models to prepare loader functions.

    Is called once during startup of the application.

    As an example, an excerpt from one of the biggest models: ProductBlockTable
        <class 'orchestrator.db.models.ProductBlockTable'>: {
          'products': [
            AttrLoader(
              loader_fn=<function selectinload at 0x...>,
              attr=<sqlalchemy.orm.attributes.InstrumentedAttribute object at 0x...>,
              next_model=<class 'orchestrator.db.models.ProductTable'>
            )
          ],
          'in_use_by': [
            AttrLoader(
              loader_fn=<function selectinload at 0x...>,
              attr=<sqlalchemy.orm.attributes.InstrumentedAttribute object at 0x...>,
              next_model=<class 'orchestrator.db.models.ProductBlockTable'>
            ),
            AttrLoader(
              loader_fn=<function joinedload at 0x...>,
              attr=<sqlalchemy.orm.attributes.InstrumentedAttribute object at 0x...>,
              next_model=<class 'orchestrator.db.models.ProductBlockRelationTable'>
            )
          ],
          ...
        }
    """
    for model in ALL_DB_MODELS:
        _MODEL_LOADERS[model] = dict(_inspect_model(model))


def lookup_attr_loaders(model: type[DbBaseModel], attr: str) -> list[AttrLoader]:
    """Return loader(s) for an attribute on the given model."""
    return _MODEL_LOADERS.get(model, {}).get(attr, [])


def join_attr_loaders(loaders: list[AttrLoader]) -> Load | None:
    """Given 1 or more attribute loaders, instantiate and chain them together."""
    if not loaders:
        return None

    first_loader, *other_loaders = loaders

    loader_fn = first_loader.loader_fn(first_loader.attr)
    if not other_loaders:
        return loader_fn

    def chain_loader_func(final_loader: Load, next: AttrLoader) -> Load:
        return getattr(final_loader, next.loader_fn.__name__)(next.attr)

    return reduce(chain_loader_func, other_loaders, loader_fn)
