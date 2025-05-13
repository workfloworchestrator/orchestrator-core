# Copyright 2019-2025 SURF, ESnet, GÉANT.
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
import itertools
from collections import defaultdict
from datetime import datetime
from inspect import get_annotations, isclass
from itertools import groupby, zip_longest
from operator import attrgetter
from typing import (
    Any,
    Callable,
    ClassVar,
    Iterable,
    Mapping,
    Optional,
    TypeVar,
    Union,
    cast,
    get_args,
    get_type_hints,
)
from uuid import UUID, uuid4

import structlog
from more_itertools import bucket, first, flatten, one, only
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.fields import PrivateAttr
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from orchestrator.db import (
    ProductBlockTable,
    ProductTable,
    SubscriptionInstanceRelationTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    db,
)
from orchestrator.db.queries.subscription_instance import get_subscription_instance_dict
from orchestrator.domain.helpers import (
    _to_product_block_field_type_iterable,
    get_root_blocks_to_instance_ids,
    no_private_attrs,
)
from orchestrator.domain.lifecycle import (
    ProductLifecycle,
    lookup_specialized_type,
    register_specialized_type,
    validate_lifecycle_status,
)
from orchestrator.domain.subscription_instance_transform import field_transformation_rules, transform_instance_fields
from orchestrator.services.products import get_product_by_id
from orchestrator.types import (
    SAFE_USED_BY_TRANSITIONS_FOR_STATUS,
    SubscriptionLifecycle,
    filter_nonetype,
    get_origin_and_args,
    get_possible_product_block_types,
    is_list_type,
    is_of_type,
    is_optional_type,
    is_union_type,
    list_factory,
)
from orchestrator.utils.datetime import nowtz
from orchestrator.utils.docs import make_product_block_docstring, make_subscription_model_docstring
from pydantic_forms.types import State, UUIDstr

logger = structlog.get_logger(__name__)


class ProductNotInRegistryError(Exception):
    pass


T = TypeVar("T")  # pragma: no mutate
S = TypeVar("S", bound="SubscriptionModel")  # pragma: no mutate
B = TypeVar("B", bound="ProductBlockModel")  # pragma: no mutate


class DomainModel(BaseModel):
    """Base class for domain models.

    Contains all common Product block/Subscription instance code
    """

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    __base_type__: ClassVar[type["DomainModel"] | None] = None  # pragma: no mutate
    _product_block_fields_: ClassVar[dict[str, Any]]
    _non_product_block_fields_: ClassVar[dict[str, type]]

    def __init_subclass__(cls, *args: Any, lifecycle: list[SubscriptionLifecycle] | None = None, **kwargs: Any) -> None:
        pass

    def __eq__(self, other: Any) -> bool:
        # PrivateAttr fields are excluded from both objects during the equality check.
        # Added for #652 primarily because ProductBlockModel._db_model is now lazy loaded.
        with no_private_attrs(self), no_private_attrs(other):
            return super().__eq__(other)

    @classmethod
    def __pydantic_init_subclass__(
        cls,
        *args: Any,
        lifecycle: list[SubscriptionLifecycle] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__pydantic_init_subclass__()
        cls._find_special_fields()

        if kwargs.keys():
            logger.warning(
                "Unexpected keyword arguments in domain model class",  # pragma: no mutate
                class_name=cls.__name__,
                kwargs=kwargs.keys(),
            )

        if not lifecycle:
            return

        # Check if dependency subscription instance models conform to the same lifecycle
        for product_block_field_name, product_block_field_type in cls._get_depends_on_product_block_types().items():
            field_types = _to_product_block_field_type_iterable(product_block_field_type)

            for lifecycle_status, field_type in itertools.product(lifecycle, field_types):
                validate_lifecycle_status(product_block_field_name, field_type, lifecycle_status)

    @classmethod
    def _get_depends_on_product_block_types(
        cls,
    ) -> dict[str, type["ProductBlockModel"] | tuple[type["ProductBlockModel"]]]:
        """Return all the product block model types.

        This strips any List[], Optional[] or Annotated[] types.
        """
        result = {}
        for product_block_field_name, product_block_field_type in cls._product_block_fields_.items():
            field_type: type["ProductBlockModel"] | tuple[type["ProductBlockModel"]]
            if is_union_type(product_block_field_type) and not is_optional_type(product_block_field_type):
                # exclude non-Optional Unions as they contain more than one useful element.
                _origin, args = get_origin_and_args(product_block_field_type)
                field_type = cast(tuple[type[ProductBlockModel]], args)
            elif is_list_type(product_block_field_type) or (
                is_optional_type(product_block_field_type) and len(get_args(product_block_field_type)) <= 2
            ):
                _origin, args = get_origin_and_args(product_block_field_type)
                field_type = first(args)
            else:
                field_type = product_block_field_type

            result[product_block_field_name] = field_type
        return result

    @classmethod
    def _find_special_fields(cls) -> None:
        """Make and store a list of resource_type fields and product block fields."""
        cls._non_product_block_fields_ = {}
        cls._product_block_fields_ = {}

        annotations = get_annotations(cls)

        # Retrieve type hints with evaluated ForwardRefs (for nested blocks) and extra annotations
        type_hints = get_type_hints(cls, localns={cls.__name__: cls}, include_extras=True)

        # But this also returns inherited fields so cross-check against the annotations
        final_annotations = {k: type_hints[k] for k in annotations}

        for field_name, field_type in final_annotations.items():
            if field_name.startswith("_"):
                continue

            try:
                is_product_block_field = (
                    is_union_type(field_type, DomainModel)
                    or is_list_type(field_type, DomainModel)
                    or is_optional_type(field_type, DomainModel)
                    or is_of_type(field_type, DomainModel)
                )
            except TypeError:
                # issubclass does not work on typing types
                is_product_block_field = False

            # Figure out if this field_name has an alias. Needed sometimes for serializable properties that
            # have a 'real' property with the same name that has a field alias.
            if (field := cls.model_fields.get(field_name)) and field.alias:
                field_name = field.alias

            # We only want fields that are on this class and not on the related product blocks
            if is_product_block_field:
                cls._product_block_fields_[field_name] = field_type
            else:
                cls._non_product_block_fields_[field_name] = field_type

    @classmethod
    def _init_instances(  # noqa: C901
        cls, subscription_id: UUID, skip_keys: set[str] | None = None
    ) -> dict[str, Union[list["ProductBlockModel"], "ProductBlockModel", None]]:
        """Initialize default subscription instances.

        When a new domain model is created that is not loaded from an existing subscription.
        We also create all subscription instances for it. This function does that.

        Args:
            subscription_id: The UUID of the subscription
            skip_keys: set of fields on the class to skip when creating dummy instances.

        Returns:
            A dict with instances to pass to the new model
        """
        if skip_keys is None:
            skip_keys = set()

        product_block_field_names = set(cls._product_block_fields_) - skip_keys
        return {
            product_block_field_name: cls._init_instance(product_block_field_name, subscription_id)
            for product_block_field_name in product_block_field_names
        }

    @classmethod
    def _init_instance(
        cls, product_block_field_name: str, subscription_id: UUID
    ) -> Union["ProductBlockModel", list["ProductBlockModel"], None]:
        """Initialize a default subscription instance."""
        product_block_field_type = cls._product_block_fields_[product_block_field_name]

        if is_list_type(product_block_field_type):
            return list_factory(product_block_field_type, subscription_id=subscription_id)

        if is_optional_type(product_block_field_type, ProductBlockModel):
            return None

        if is_union_type(product_block_field_type):
            raise ValueError(
                "Union Types must always be `Optional` when calling `.new().` We are unable to detect which "
                "type to intialise and Union types always cross subscription boundaries."
            )

        product_block_model = product_block_field_type
        # Scalar field of a ProductBlockModel expects 1 instance
        return product_block_model.new(subscription_id=subscription_id)

    @classmethod
    def _load_instances(  # noqa: C901
        cls,
        db_instances: list[SubscriptionInstanceTable],
        status: SubscriptionLifecycle,
        match_domain_attr: bool = True,
        in_use_by_id_boundary: UUID | None = None,
    ) -> dict[str, Optional["ProductBlockModel"] | list["ProductBlockModel"]]:
        """Load subscription instances for this domain model.

        When a new domain model is loaded from an existing subscription we also load all
        subscription instances for it. This function does that.

        Args:
            db_instances: list of database models to load from
            status: SubscriptionLifecycle of subscription to check if models match
            match_domain_attr: Match domain attribute on relations [1]
            in_use_by_id_boundary: Match domain attribute on relations with this in_use_by_id [1]

        Note [1]: only use these parameters when loading product blocks that are in use by another product block.

        Returns:
            A dict with instances to pass to the new model

        """

        instances: dict[str, ProductBlockModel | None | list[ProductBlockModel]] = {}

        def keyfunc(i: SubscriptionInstanceTable) -> str:
            return i.product_block.name

        sorted_instances = sorted(db_instances, key=keyfunc)
        grouped_instances = {k: list(g) for k, g in groupby(sorted_instances, keyfunc)}

        def match_domain_model_attr_if_possible(field_name: str) -> Callable:
            def domain_filter(instance: SubscriptionInstanceTable) -> bool:
                """Match domain model attributes.

                This helper is necessary to filter through all relations in a subscription. Not all subscriptions have a
                domain model attribute that is set as it is not always necessary. However when it is set, it is necessary
                to filter through instances depending on that attribute.

                Args:
                    instance: depends on subscription instance

                Returns:
                    Boolean of match.

                """
                # We don't match on the product_blocks directly under subscriptions. They don't have in_use_by relations to those
                if not match_domain_attr:
                    return True

                def include_relation(relation: SubscriptionInstanceRelationTable) -> bool:
                    return bool(relation.domain_model_attr) and (
                        not in_use_by_id_boundary or relation.in_use_by_id == in_use_by_id_boundary
                    )

                attr_names = {
                    rel.domain_model_attr for rel in instance.in_use_by_block_relations if include_relation(rel)
                }

                # We can assume true if no domain_model_attr is set.
                return not attr_names or field_name in attr_names

            return domain_filter

        product_block_model_list: list[ProductBlockModel] = []
        for product_block_field_name, product_block_field_type in cls._product_block_fields_.items():
            filter_func = match_domain_model_attr_if_possible(product_block_field_name)

            possible_product_block_types = flatten_product_block_types(product_block_field_type)
            field_type_names = list(possible_product_block_types.keys())
            filtered_instances = flatten([grouped_instances.get(name, []) for name in field_type_names])
            instance_list = list(filter(filter_func, filtered_instances))

            if is_list_type(product_block_field_type):
                if product_block_field_name not in grouped_instances:
                    product_block_model_list = []

                product_block_model_list.extend(
                    possible_product_block_types[instance.product_block.name].from_db(
                        subscription_instance=instance, status=status
                    )
                    for instance in instance_list
                )

                instances[product_block_field_name] = product_block_model_list
            else:
                instance = only(instance_list)
                if not is_optional_type(product_block_field_type) and instance is None:
                    raise ValueError("Required subscription instance is missing in database")

                if is_optional_type(product_block_field_type) and instance is None:
                    instances[product_block_field_name] = None
                elif instance:
                    assert (  # noqa: S101
                        len(possible_product_block_types) is not None
                    ), "Product block model has not been resolved. Unable to continue"
                    instances[product_block_field_name] = possible_product_block_types[
                        instance.product_block.name
                    ].from_db(subscription_instance=instance, status=status)
        return instances

    @classmethod
    def _data_from_lifecycle(cls, other: "DomainModel", status: SubscriptionLifecycle, subscription_id: UUID) -> dict:
        data = other.model_dump()

        for field_name, field_type in cls._product_block_fields_.items():
            value = getattr(other, field_name)
            if value is None:
                continue

            _origin, args = get_origin_and_args(field_type)
            if is_list_type(field_type):
                data[field_name] = []
                list_field_type = one(args)
                possible_product_block_types = get_possible_product_block_types(list_field_type)

                for item in value:
                    data[field_name].append(
                        possible_product_block_types[item.name]._from_other_lifecycle(item, status, subscription_id)
                    )
            else:
                if is_union_type(field_type):
                    if is_optional_type(field_type):
                        data[field_name] = None
                    for f_type in filter_nonetype(args):
                        if f_type.name == value.name:
                            field_type = f_type
                            break
                    else:
                        logger.warning(
                            "Cannot determine type for product block field value",
                            field_name=field_name,
                            field_type=field_type,
                            value_name=value.name,
                        )
                        continue

                data[field_name] = field_type._from_other_lifecycle(value, status, subscription_id)
        return data

    def _save_instances(
        self, subscription_id: UUID, status: SubscriptionLifecycle
    ) -> tuple[list[SubscriptionInstanceTable], dict[str, list[SubscriptionInstanceTable]]]:
        """Save subscription instances for this domain model.

        When a domain model is saved to the database we need to save all depends_on subscription instances for it.

        Args:
            subscription_id: The subscription id
            status: SubscriptionLifecycle of subscription to check if models match

        Returns:
            A list with instances which are saved and a dict with direct depends_on relations.

        """
        saved_instances: list[SubscriptionInstanceTable] = []
        depends_on_instances: dict[str, list[SubscriptionInstanceTable]] = {}

        self._check_duplicate_instance_relations()

        for product_block_field, product_block_field_type in self._product_block_fields_.items():
            product_block_models = getattr(self, product_block_field)
            if is_list_type(product_block_field_type):
                field_instance_list = []
                for product_block_model in product_block_models:
                    saved, depends_on_instance = product_block_model.save(
                        subscription_id=subscription_id, status=status
                    )
                    field_instance_list.append(depends_on_instance)
                    saved_instances.extend(saved)
                depends_on_instances[product_block_field] = field_instance_list
            elif (
                is_optional_type(product_block_field_type) or is_union_type(product_block_field_type)
            ) and product_block_models is None:
                pass
            else:
                saved, depends_on_instance = product_block_models.save(subscription_id=subscription_id, status=status)
                depends_on_instances[product_block_field] = [depends_on_instance]
                saved_instances.extend(saved)

        return saved_instances, depends_on_instances

    def _check_duplicate_instance_relations(self) -> None:
        """Check that there are no product block fields referring to the same instance.

        A ValueError is raised if this is the case.
        """

        def get_id(product_block: ProductBlockModel) -> UUID:
            return product_block.subscription_instance_id

        def get_ids(field_name: str) -> Iterable[tuple[str, UUID]]:
            match getattr(self, field_name):
                case list() as value_list:
                    blocks = (value for value in value_list if isinstance(value, ProductBlockModel))
                    yield from ((f"{field_name}.{index}", get_id(block)) for index, block in enumerate(blocks))
                case ProductBlockModel() as block:
                    yield field_name, get_id(block)

        def to_fields(mm: Iterable[tuple[str, UUID]]) -> list[str]:
            return [x[0] for x in mm]

        field_id_tuples = flatten(get_ids(field_name) for field_name in self._product_block_fields_)
        id_buckets = bucket(field_id_tuples, lambda x: x[1])
        id_fields_tuples = ((id_, to_fields(id_buckets[id_])) for id_ in id_buckets)
        duplicates = [(id_, fields) for id_, fields in id_fields_tuples if len(fields) > 1]
        if duplicates:
            details = "; ".join(f"instance {id_} is used in fields {fields}" for id_, fields in duplicates)
            raise ValueError(f"Cannot link the same subscription instance multiple times: {details}")


def flatten_product_block_types(product_block_field_type: Any) -> dict[str, type["ProductBlockModel"]]:
    """Extract product block types and return mapping of product block names to product block classes."""
    product_block_model: Any = product_block_field_type
    if is_list_type(product_block_field_type):
        _origin, args = get_origin_and_args(product_block_field_type)
        product_block_model = one(args)
    return get_possible_product_block_types(product_block_model)


def get_depends_on_product_block_type_list(
    product_block_types: dict[str, type["ProductBlockModel"] | tuple[type["ProductBlockModel"]]],
) -> list[type["ProductBlockModel"]]:
    product_blocks_types_in_model = []
    for product_block_type in product_block_types.values():
        if is_union_type(product_block_type):
            _origin, args = get_origin_and_args(product_block_type)
            product_blocks_types_in_model.extend(list(filter_nonetype(args)))
        else:
            product_blocks_types_in_model.append(product_block_type)

    if product_blocks_types_in_model and isinstance(first(product_blocks_types_in_model), tuple):
        return one(product_blocks_types_in_model)

    return product_blocks_types_in_model


class ProductBlockModel(DomainModel):
    r"""This is the base class for all product block models.

    This class should have been called SubscriptionInstanceModel.

    ProductTable Blocks are represented as dataclasses with pydantic runtime validation.

    Different stages of a subscription lifecycle could require different product block
    definition.Mainly to support mandatory fields when a subscription is active. To support
    this a lifecycle specific product block definition can be created by subclassing the
    generic product block with keyword argument 'lifecycle' and overriding its fields.

    All product blocks are related to a database ProductBlockTable object through the `product_block_name`
    that is given as class keyword argument.

    Define a product block:

        >>> class BlockInactive(ProductBlockModel, product_block_name="Virtual Circuit"):
        ...    int_field: Optional[int] = None
        ...    str_field: Optional[str] = None

        >>> class Block(BlockInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        ...    int_field: int
        ...    str_field: str

    This example defines a product_block with two different contraints based on lifecycle. `Block` is valid only for `ACTIVE`
    And `BlockInactive` for all other states.
    `product_block_name` must be defined on the base class and need not to be defined on the others

    Create a new empty product block:

        >>> example1 = BlockInactive()  # doctest: +SKIP

    Create a new instance based on a dict in the state:

        >>> example2 = BlockInactive(**state)  # doctest:+SKIP

    To retrieve a ProductBlockModel from the database:

        >>> BlockInactive.from_db(subscription_instance_id)  # doctest:+SKIP
    """

    registry: ClassVar[dict[str, type["ProductBlockModel"]]] = {}  # pragma: no mutate
    __names__: ClassVar[set[str]] = set()
    product_block_id: ClassVar[UUID]
    description: ClassVar[str]
    tag: ClassVar[str]
    _db_model: SubscriptionInstanceTable | None = PrivateAttr(default=None)

    # Product block name. This needs to be an instance var because its part of the API (we expose it to the frontend)
    # Is actually optional since abstract classes don't have it.
    # TODO #427 name is used as both a ClassVar and a pydantic Field, for which Pydantic 2.x raises
    #  warnings (which may become errors)
    name: str | None
    subscription_instance_id: UUID
    owner_subscription_id: UUID
    label: str | None = None

    @classmethod
    def _fix_pb_data(cls) -> None:
        if not cls.name:
            raise ValueError(f"Cannot create instance of abstract class. Use one of {cls.__names__}")

        # Would have been nice to do this in __init_subclass__ but that runs outside the app context so we can't
        # access the db. So now we do it just before we instantiate the instance
        if not hasattr(cls, "product_block_id"):
            product_block = db.session.scalars(
                select(ProductBlockTable).filter(ProductBlockTable.name == cls.name)
            ).one()
            cls.product_block_id = product_block.product_block_id
            cls.description = product_block.description
            cls.tag = product_block.tag

    @classmethod
    def __pydantic_init_subclass__(  # type: ignore[override]
        cls,
        *,
        product_block_name: str | None = None,
        lifecycle: list[SubscriptionLifecycle] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__pydantic_init_subclass__(lifecycle=lifecycle, **kwargs)

        if product_block_name is not None:
            # This is a concrete product block base class (so not a abstract super class or a specific lifecycle version)
            cls.name = product_block_name
            cls.__base_type__ = cls
            cls.__names__ = {cls.name}
            cls.registry[cls.name] = cls
        elif lifecycle is None:
            # Abstract class, no product block name
            cls.name = None
            cls.__names__ = set()

        # For everything except abstract classes
        if cls.name is not None:
            register_specialized_type(cls, lifecycle)

            # Add ourselves to any super class. That way we can match a superclass to an instance when loading
            for klass in cls.__mro__:
                if issubclass(klass, ProductBlockModel):
                    klass.__names__.add(cls.name)

        cls.__doc__ = make_product_block_docstring(cls, lifecycle)

    @classmethod
    def diff_product_block_in_database(cls) -> dict[str, set[str]]:
        """Return any differences between the attrs defined on the domain model and those on product blocks in the database.

        This is only needed to check if the domain model and database models match which would be done during testing...
        """
        if not cls.name:
            # This is a superclass we can't check that
            return {}

        product_block_db = db.session.scalars(
            select(ProductBlockTable).where(ProductBlockTable.name == cls.name)
        ).one_or_none()
        product_blocks_in_db = {pb.name for pb in product_block_db.depends_on} if product_block_db else set()

        product_blocks_in_model = cls._get_depends_on_product_block_types()
        product_blocks_types_in_model = get_depends_on_product_block_type_list(product_blocks_in_model)

        product_blocks_in_model = set(
            flatten(map(attrgetter("__names__"), product_blocks_types_in_model))
        )  # type: ignore

        missing_product_blocks_in_db = product_blocks_in_model - product_blocks_in_db  # type: ignore
        missing_product_blocks_in_model = product_blocks_in_db - product_blocks_in_model  # type: ignore

        resource_types_model = set(cls._non_product_block_fields_)
        resource_types_db = {rt.resource_type for rt in product_block_db.resource_types} if product_block_db else set()

        missing_resource_types_in_db = resource_types_model - resource_types_db
        missing_resource_types_in_model = resource_types_db - resource_types_model

        logger.debug(
            "ProductBlockTable blocks diff",
            product_block_db=product_block_db.name if product_block_db else None,
            product_blocks_in_db=product_blocks_in_db,
            product_blocks_in_model=product_blocks_in_model,
            resource_types_db=resource_types_db,
            resource_types_model=resource_types_model,
            missing_product_blocks_in_db=missing_product_blocks_in_db,
            missing_product_blocks_in_model=missing_product_blocks_in_model,
            missing_resource_types_in_db=missing_resource_types_in_db,
            missing_resource_types_in_model=missing_resource_types_in_model,
        )

        missing_data: dict[str, Any] = {}
        for product_block_model in product_blocks_types_in_model:
            if product_block_model.name == cls.name or product_block_model.name in missing_data:
                continue
            missing_data.update(product_block_model.diff_product_block_in_database())

        diff: dict[str, set[str]] = {
            k: v
            for k, v in {
                "missing_product_blocks_in_db": missing_product_blocks_in_db,
                "missing_product_blocks_in_model": missing_product_blocks_in_model,
                "missing_resource_types_in_db": missing_resource_types_in_db,
                "missing_resource_types_in_model": missing_resource_types_in_model,
            }.items()
            if v
        }

        if diff:
            missing_data[cls.name] = diff

        return missing_data

    @classmethod
    def new(cls: type[B], subscription_id: UUID, **kwargs: Any) -> B:
        """Create a new empty product block.

        We need to use this instead of the normal constructor because that assumes you pass in
        all required values. That is cumbersome since that means creating a tree of product blocks.

        This is similar to `from_product_id()`
        """
        sub_instances = cls._init_instances(subscription_id, set(kwargs.keys()))

        subscription_instance_id = uuid4()

        # Make sure product block stuff is already set if new is the first usage of this class
        cls._fix_pb_data()

        db_model = SubscriptionInstanceTable(
            product_block_id=cls.product_block_id,
            subscription_instance_id=subscription_instance_id,
            subscription_id=subscription_id,
        )
        db.session.enable_relationship_loading(db_model)

        if kwargs_name := kwargs.pop("name", None):
            # Not allowed to change the product block model name at runtime. This is only possible through
            # the `product_block_name=..` metaclass parameter
            logger.warning("Ignoring `name` keyword to ProductBlockModel.new()", rejected_name=kwargs_name)
        model = cls(
            name=cls.name,
            subscription_instance_id=subscription_instance_id,
            owner_subscription_id=subscription_id,
            label=db_model.label,
            **sub_instances,
            **kwargs,
        )
        model.db_model = db_model
        return model

    @classmethod
    def _load_instances_values(cls, instance_values: list[SubscriptionInstanceValueTable]) -> dict[str, str]:
        """Load non product block fields (instance values).

        Args:
            instance_values: List of instance values from database

        Returns:
            Dict of fields to use for constructor

        """
        instance_values_dict: State = {}
        list_field_names = set()

        # Set default values
        for field_name, field_type in cls._non_product_block_fields_.items():
            # Ensure that empty lists are handled OK
            if is_list_type(field_type):
                instance_values_dict[field_name] = []
                list_field_names.add(field_name)
            elif is_optional_type(field_type):
                # Initialize "optional required" fields
                instance_values_dict[field_name] = None

        for siv in instance_values:
            # check the type of the siv in the instance and act accordingly: only lists and scalar values supported
            resource_type_name = siv.resource_type.resource_type
            if resource_type_name in list_field_names:
                instance_values_dict[resource_type_name].append(siv.value)
            else:
                instance_values_dict[resource_type_name] = siv.value

        return instance_values_dict

    @classmethod
    def _from_other_lifecycle(
        cls: type[B],
        other: "ProductBlockModel",
        status: SubscriptionLifecycle,
        subscription_id: UUID,
    ) -> B:
        """Create new domain model from instance while changing the status.

        This makes sure we always have a specific instance.
        """
        if not cls.__base_type__:
            cls = ProductBlockModel.registry.get(other.name, cls)  # type:ignore
            cls = lookup_specialized_type(cls, status)

        data = cls._data_from_lifecycle(other, status, subscription_id)

        cls._fix_pb_data()
        model = cls(**data)
        model.db_model = other.db_model
        return model

    @classmethod
    def from_db(
        cls: type[B],
        subscription_instance_id: UUID | None = None,
        subscription_instance: SubscriptionInstanceTable | None = None,
        status: SubscriptionLifecycle | None = None,
    ) -> B:
        """Create a product block based on a subscription instance from the database.

        This function is similar to `from_subscription()`

            >>> subscription_instance_id = KNOWN_UUID_IN_DB  # doctest:+SKIP
            >>> si_from_db = db.SubscriptionInstanceTable.query.get(subscription_instance_id)  # doctest:+SKIP
            >>> example3 = ProductBlockModel.from_db(subscription_instance=si_from_db)  # doctest:+SKIP
            >>> example4 = ProductBlockModel.from_db(subscription_instance_id=subscription_instance_id)  # doctest:+SKIP
        """
        # Fill values from actual subscription
        if subscription_instance_id:
            subscription_instance = db.session.get(SubscriptionInstanceTable, subscription_instance_id)
        if subscription_instance:
            subscription_instance_id = subscription_instance.subscription_instance_id
        assert subscription_instance_id  # noqa: S101
        assert subscription_instance  # noqa: S101

        if not status:
            status = SubscriptionLifecycle(subscription_instance.subscription.status)

        if not cls.__base_type__:
            cls = ProductBlockModel.registry.get(subscription_instance.product_block.name, cls)  # type:ignore
            cls = lookup_specialized_type(cls, status)

        elif not issubclass(cls, lookup_specialized_type(cls, status)):
            raise ValueError(f"{cls} is not valid for lifecycle {status}")

        label = subscription_instance.label

        instance_values = cls._load_instances_values(subscription_instance.values)
        sub_instances = cls._load_instances(
            subscription_instance.depends_on,
            status,
            match_domain_attr=True,
            in_use_by_id_boundary=subscription_instance_id,
        )

        cls._fix_pb_data()
        try:
            model = cls(
                name=cls.name,
                subscription_instance_id=subscription_instance_id,
                owner_subscription_id=subscription_instance.subscription_id,
                label=label,
                subscription=subscription_instance.subscription,
                **instance_values,  # type: ignore
                **sub_instances,
            )
            model.db_model = subscription_instance

            return model
        except ValidationError:
            logger.exception(
                "Subscription is not correct in database",
                loaded_instance_values=instance_values,
                loaded_sub_instances=sub_instances,
            )
            raise

    def _save_instance_values(
        self, product_block: ProductBlockTable, current_values: list[SubscriptionInstanceValueTable]
    ) -> list[SubscriptionInstanceValueTable]:
        """Save non product block fields (instance values).

        Returns:
            List of database instances values to save

        """
        resource_types = {rt.resource_type: rt for rt in product_block.resource_types}
        current_values_dict: dict[str, list[SubscriptionInstanceValueTable]] = defaultdict(list)
        for siv in current_values:
            current_values_dict[siv.resource_type.resource_type].append(siv)

        subscription_instance_values = []
        for field_name, field_type in self._non_product_block_fields_.items():
            assert (  # noqa: S101
                field_name in resource_types
            ), f"Domain model {self.__class__} does not match the ProductBlockTable {product_block.name}, missing: {field_name} {resource_types}"

            resource_type = resource_types[field_name]
            value = getattr(self, field_name)
            if value is None:
                continue
            if is_list_type(field_type):
                for val, siv in zip_longest(value, current_values_dict[field_name]):
                    if val is not None:
                        if siv:
                            siv.value = str(val)
                            subscription_instance_values.append(siv)
                        else:
                            subscription_instance_values.append(
                                SubscriptionInstanceValueTable(resource_type=resource_type, value=str(val))
                            )
            else:
                if field_name in current_values_dict:
                    current_value = current_values_dict[field_name][0]
                    current_value.value = str(value)
                    subscription_instance_values.append(current_value)
                else:
                    subscription_instance_values.append(
                        SubscriptionInstanceValueTable(resource_type=resource_type, value=str(value))
                    )
        return subscription_instance_values

    def _set_instance_domain_model_attrs(
        self,
        subscription_instance: SubscriptionInstanceTable,
        subscription_instance_mapping: dict[str, list[SubscriptionInstanceTable]],
    ) -> None:
        """Save the domain model attribute to the database.

        This function iterates through the subscription instances and stores the domain model attribute in the
        hierarchy relationship.

        Args:
            subscription_instance: The subscription instance object.
            subscription_instance_mapping: a mapping of the domain model attribute a underlying instances

        Returns:
            None

        """
        depends_on_block_relations = []
        # Set the domain_model_attrs in the database
        for domain_model_attr, instances in subscription_instance_mapping.items():
            instance: SubscriptionInstanceTable
            for index, instance in enumerate(instances):
                relation = SubscriptionInstanceRelationTable(
                    in_use_by_id=subscription_instance.subscription_instance_id,
                    depends_on_id=instance.subscription_instance_id,
                    order_id=index,
                    domain_model_attr=domain_model_attr,
                )
                depends_on_block_relations.append(relation)
        subscription_instance.depends_on_block_relations = depends_on_block_relations

    def save(
        self, *, subscription_id: UUID, status: SubscriptionLifecycle
    ) -> tuple[list[SubscriptionInstanceTable], SubscriptionInstanceTable]:
        """Save the current model instance to the database.

        This means saving the whole tree of subscription instances and separately saving all instance
        values for this instance. This is called automatically when you return a subscription to the state
        in a workflow step.

        Args:
            status: current SubscriptionLifecycle to check if all constraints match
            subscription_id: Optional subscription id needed if this is a new model

        Returns:
            List of saved instances

        """
        if not self.name:
            raise ValueError(f"Cannot create instance of abstract class. Use one of {self.__names__}")

        # Make sure we have a valid subscription instance database model
        subscription_instance: SubscriptionInstanceTable | None = db.session.get(
            SubscriptionInstanceTable, self.subscription_instance_id
        )
        if subscription_instance:
            # Make sure we do not use a mapped session.
            db.session.refresh(subscription_instance)

            # If this is a "foreign" instance we just stop saving and return it so only its relation is saved
            # We should not touch these themselves
            if self.owner_subscription_id != subscription_id:
                return [], subscription_instance

            self.db_model = subscription_instance
        elif subscription_instance := self.db_model:
            # We only need to add to the session if the subscription_instance does not exist.
            db.session.add(subscription_instance)
        else:
            raise ValueError("Cannot save ProductBlockModel without a db_model")

        subscription_instance.subscription_id = subscription_id

        db.session.flush()

        # Everything is ok, make sure we are of the right class
        specialized_type = lookup_specialized_type(self.__class__, status)
        if specialized_type and not isinstance(self, specialized_type):
            raise ValueError(
                f"Lifecycle status {status} requires specialized type {specialized_type!r}, was: {type(self)!r}"
            )

        # Actually save stuff
        subscription_instance.label = self.label
        subscription_instance.values = self._save_instance_values(
            subscription_instance.product_block, subscription_instance.values
        )

        sub_instances, depends_on_instances = self._save_instances(subscription_id, status)

        # Save the subscription instances relations.
        self._set_instance_domain_model_attrs(subscription_instance, depends_on_instances)

        return sub_instances + [subscription_instance], subscription_instance

    @property
    def subscription(self) -> SubscriptionTable | None:
        return self.db_model.subscription if self.db_model else None

    @property
    def db_model(self) -> SubscriptionInstanceTable | None:
        if not self._db_model:
            self._db_model = db.session.execute(
                select(SubscriptionInstanceTable).where(
                    SubscriptionInstanceTable.subscription_instance_id == self.subscription_instance_id
                )
            ).scalar_one_or_none()
        return self._db_model

    @db_model.setter
    def db_model(self, value: SubscriptionInstanceTable) -> None:
        self._db_model = value

    @property
    def in_use_by(self) -> list[SubscriptionInstanceTable]:  # TODO check where used, might need eagerloading
        """This provides a list of product blocks that depend on this product block."""
        return self.db_model.in_use_by if self.db_model else []

    @property
    def depends_on(self) -> list[SubscriptionInstanceTable]:  # TODO check where used, might need eagerloading
        """This provides a list of product blocks that this product block depends on."""
        return self.db_model.depends_on if self.db_model else []


class ProductModel(BaseModel):
    """Represent the product as defined in the database as a dataclass."""

    model_config = ConfigDict(validate_assignment=True, validate_default=True)

    product_id: UUID
    name: str
    description: str
    product_type: str
    tag: str
    status: ProductLifecycle
    created_at: datetime | None = None
    end_date: datetime | None = None


class SubscriptionModel(DomainModel):
    r"""This is the base class for all product subscription models.

    To use this class, see the examples below:

    Definining a subscription model:

        >>> class SubscriptionInactive(SubscriptionModel, product_type="SP"):  # doctest:+SKIP
        ...    block: Optional[ProductBlockModelInactive] = None

        >>> class Subscription(BlockInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):  # doctest:+SKIP
        ...    block: ProductBlockModel

    This example defines a subscription model with two different contraints based on lifecycle. `Subscription` is valid only for `ACTIVE`
    And `SubscriptionInactive` for all other states.
    `product_type` must be defined on the base class and need not to be defined on the others

    Create a new empty subscription:

        >>> example1 = SubscriptionInactive.from_product_id(product_id, customer_id)  # doctest:+SKIP

    Create a new instance based on a dict in the state:

        >>> example2 = SubscriptionInactive(**state)  # doctest:+SKIP

    To retrieve a ProductBlockModel from the database:

        >>> SubscriptionInactive.from_subscription(subscription_id)  # doctest:+SKIP
    """

    __model_dump_cache__: ClassVar[dict[UUID, "SubscriptionModel"] | None] = None

    product: ProductModel
    customer_id: str
    _db_model: SubscriptionTable | None = PrivateAttr(default=None)
    subscription_id: UUID = Field(default_factory=uuid4)  # pragma: no mutate
    description: str = "Initial subscription"  # pragma: no mutate
    status: SubscriptionLifecycle = SubscriptionLifecycle.INITIAL  # pragma: no mutate
    insync: bool = False  # pragma: no mutate
    start_date: datetime | None = None  # pragma: no mutate
    end_date: datetime | None = None  # pragma: no mutate
    note: str | None = None  # pragma: no mutate
    version: int = 1  # pragma: no mutate

    def __new__(cls, *args: Any, status: SubscriptionLifecycle | None = None, **kwargs: Any) -> "SubscriptionModel":
        # status can be none if created during change_lifecycle
        if status and not issubclass(cls, lookup_specialized_type(cls, status)):
            raise ValueError(f"{cls} is not valid for status {status}")

        return super().__new__(cls)

    @classmethod
    def __pydantic_init_subclass__(  # type: ignore[override]
        cls, is_base: bool = False, lifecycle: list[SubscriptionLifecycle] | None = None, **kwargs: Any
    ) -> None:
        super().__pydantic_init_subclass__(lifecycle=lifecycle, **kwargs)

        if is_base:
            cls.__base_type__ = cls

        if is_base or lifecycle:
            register_specialized_type(cls, lifecycle)

        cls.__doc__ = make_subscription_model_docstring(cls, lifecycle)

    @classmethod
    def diff_product_in_database(cls, product_id: UUID) -> dict[str, dict[str, set[str] | dict[str, set[str]]]]:
        """Return any differences between the attrs defined on the domain model and those on product blocks in the database.

        This is only needed to check if the domain model and database models match which would be done during testing...
        """
        product_db = db.session.get(ProductTable, product_id)
        product_blocks_in_db = {pb.name for pb in product_db.product_blocks} if product_db else set()

        product_blocks_in_model = cls._get_depends_on_product_block_types()
        product_blocks_types_in_model = get_depends_on_product_block_type_list(product_blocks_in_model)

        product_blocks_in_model = set(
            flatten(map(attrgetter("__names__"), product_blocks_types_in_model))
        )  # type: ignore

        missing_product_blocks_in_db = product_blocks_in_model - product_blocks_in_db  # type: ignore
        missing_product_blocks_in_model = product_blocks_in_db - product_blocks_in_model  # type: ignore

        fixed_inputs_model = set(cls._non_product_block_fields_)
        fixed_inputs_in_db = {fi.name for fi in product_db.fixed_inputs} if product_db else set()

        missing_fixed_inputs_in_db = fixed_inputs_model - fixed_inputs_in_db
        missing_fixed_inputs_in_model = fixed_inputs_in_db - fixed_inputs_model

        logger.debug(
            "ProductTable blocks diff",
            product_block_db=product_db.name if product_db else None,
            product_blocks_in_db=product_blocks_in_db,
            product_blocks_in_model=product_blocks_in_model,
            fixed_inputs_in_db=fixed_inputs_in_db,
            fixed_inputs_model=fixed_inputs_model,
            missing_product_blocks_in_db=missing_product_blocks_in_db,
            missing_product_blocks_in_model=missing_product_blocks_in_model,
            missing_fixed_inputs_in_db=missing_fixed_inputs_in_db,
            missing_fixed_inputs_in_model=missing_fixed_inputs_in_model,
        )

        missing_data_depends_on_blocks: dict[str, set[str]] = {}
        for product_block_in_model in product_blocks_types_in_model:
            missing_data_depends_on_blocks.update(product_block_in_model.diff_product_block_in_database())

        diff: dict[str, set[str] | dict[str, set[str]]] = {
            k: v
            for k, v in {
                "missing_product_blocks_in_db": missing_product_blocks_in_db,
                "missing_product_blocks_in_model": missing_product_blocks_in_model,
                "missing_fixed_inputs_in_db": missing_fixed_inputs_in_db,
                "missing_fixed_inputs_in_model": missing_fixed_inputs_in_model,
                "missing_in_depends_on_blocks": missing_data_depends_on_blocks,
            }.items()
            if v
        }

        missing_data: dict[str, dict[str, set[str] | dict[str, set[str]]]] = {}
        if diff and product_db:
            missing_data[product_db.name] = diff

        return missing_data

    @classmethod
    def _load_root_instances(
        cls,
        subscription_id: UUID | UUIDstr,
    ) -> dict[str, Optional[dict] | list[dict]]:
        """Load root subscription instance(s) for this subscription model.

        When a new subscription model is loaded from an existing subscription, this function loads the entire root
        subscription instance(s) from database using an optimized postgres function. The result of that function
        is used to instantiate the root product block(s).

        The "old" method DomainModel._load_instances() would recursively load subscription instances from the
        database and individually instantiate nested blocks, more or less "manually" reconstructing the subscription.

        The "new" method SubscriptionModel._load_root_instances() takes a different approach; since it has all
        data for the root subscription instance, it can rely on Pydantic to instantiate the root block and all
        nested blocks in one go. This is also why it does not have the params `status` and `match_domain_attr` because
        this information is already encoded in the domain model of a product.
        """
        root_block_instance_ids = get_root_blocks_to_instance_ids(subscription_id)

        root_block_types = {
            field_name: list(flatten_product_block_types(product_block_type).keys())
            for field_name, product_block_type in cls._product_block_fields_.items()
        }

        def get_instances_by_block_names(block_names: list[str]) -> Iterable[dict]:
            for block_name in block_names:
                for instance_id in root_block_instance_ids.get(block_name, []):
                    yield get_subscription_instance_dict(instance_id)

        # Map root product block fields to subscription instance(s) dicts
        instances = {
            field_name: list(get_instances_by_block_names(block_names))
            for field_name, block_names in root_block_types.items()
        }

        # Transform values according to domain models (list[dict] -> dict, add None as default for optionals)
        rules = {
            klass.name: field_transformation_rules(klass) for klass in ProductBlockModel.registry.values() if klass.name
        }
        for instance_list in instances.values():
            for instance in instance_list:
                transform_instance_fields(rules, instance)

        # Support the (theoretical?) usecase of a list of root product blocks
        def unpack_instance_list(field_name: str, instance_list: list[dict]) -> list[dict] | dict | None:
            field_type = cls._product_block_fields_[field_name]
            if is_list_type(field_type):
                return instance_list
            return only(instance_list)

        return {
            field_name: unpack_instance_list(field_name, instance_list)
            for field_name, instance_list in instances.items()
        }

    @classmethod
    def from_product_id(
        cls: type[S],
        product_id: UUID | UUIDstr,
        customer_id: str,
        status: SubscriptionLifecycle = SubscriptionLifecycle.INITIAL,
        description: str | None = None,
        insync: bool = False,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        note: str | None = None,
        version: int = 1,
    ) -> S:
        """Use product_id (and customer_id) to return required fields of a new empty subscription."""
        # Caller wants a new instance and provided a product_id and customer_id
        product_db = db.session.get(ProductTable, product_id)
        if not product_db:
            raise KeyError("Could not find a product for the given product_id")

        product = ProductModel(
            product_id=product_db.product_id,
            name=product_db.name,
            description=product_db.description,
            product_type=product_db.product_type,
            tag=product_db.tag,
            status=product_db.status,
            created_at=product_db.created_at,
            end_date=product_db.end_date,
        )

        if description is None:
            description = f"Initial subscription of {product.description}"

        subscription_id = uuid4()
        subscription = SubscriptionTable(
            subscription_id=subscription_id,
            product_id=product_id,
            customer_id=customer_id,
            description=description,
            status=status.value,
            insync=insync,
            start_date=start_date,
            end_date=end_date,
            note=note,
            version=version,
        )
        db.session.add(subscription)

        fixed_inputs = {fi.name: fi.value for fi in product_db.fixed_inputs}
        instances = cls._init_instances(subscription_id)

        model = cls(
            product=product,
            customer_id=customer_id,
            subscription_id=subscription_id,
            description=description,
            status=status,
            insync=insync,
            start_date=start_date,
            end_date=end_date,
            note=note,
            version=version,
            **fixed_inputs,
            **instances,
        )
        model.db_model = subscription
        return model

    @classmethod
    def from_other_lifecycle(
        cls: type[S],
        other: "SubscriptionModel",
        status: SubscriptionLifecycle,
        skip_validation: bool = False,
    ) -> S:
        """Create new domain model from instance while changing the status.

        This makes sure we always have a specific instance.
        """
        if not cls.__base_type__:
            # Import here to prevent cyclic imports
            from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY

            cls = SUBSCRIPTION_MODEL_REGISTRY.get(other.product.name, cls)  # type:ignore
            cls = lookup_specialized_type(cls, status)

        # this will raise ValueError when wrong lifecycle transitions are detected in the new domain model
        if not skip_validation:
            validate_lifecycle_change(other, status)

        data = cls._data_from_lifecycle(other, status, other.subscription_id)
        data["status"] = status
        if data["start_date"] is None and status == SubscriptionLifecycle.ACTIVE:
            data["start_date"] = nowtz()
        if data["end_date"] is None and status == SubscriptionLifecycle.TERMINATED:
            data["end_date"] = nowtz()

        model = cls(**data)
        model.db_model = other._db_model

        return model

    # Some common functions shared by from_other_product and from_subscription
    @classmethod
    def _get_subscription(cls: type[S], subscription_id: UUID | UUIDstr) -> SubscriptionTable | None:

        if not isinstance(subscription_id, UUID | UUIDstr):
            raise TypeError(f"subscription_id is of type {type(subscription_id)} instead of UUID | UUIDstr")

        loaders = [
            joinedload(SubscriptionTable.product).selectinload(ProductTable.fixed_inputs),
        ]

        return db.session.get(SubscriptionTable, subscription_id, options=loaders)

    @classmethod
    def _to_product_model(cls: type[S], product: ProductTable) -> ProductModel:
        return ProductModel(
            product_id=product.product_id,
            name=product.name,
            description=product.description,
            product_type=product.product_type,
            tag=product.tag,
            status=product.status,
            created_at=product.created_at if product.created_at else None,
            end_date=product.end_date if product.end_date else None,
        )

    @classmethod
    def from_other_product(
        cls: type[S],
        old_instantiation: S,
        new_product_id: UUID | str,
        new_root: tuple[str, ProductBlockModel] | None = None,
    ) -> S:
        db_product = get_product_by_id(new_product_id)
        if not db_product:
            raise KeyError("Could not find a product for the given product_id")

        old_subscription_id = old_instantiation.subscription_id
        if not (subscription := cls._get_subscription(old_subscription_id)):
            raise ValueError(f"Subscription with id: {old_subscription_id}, does not exist")
        product = cls._to_product_model(db_product)

        status = SubscriptionLifecycle(subscription.status)

        if not cls.__base_type__:
            # Import here to prevent cyclic imports
            from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY

            cls = SUBSCRIPTION_MODEL_REGISTRY.get(subscription.product.name, cls)  # type:ignore
            cls = lookup_specialized_type(cls, status)
        elif not issubclass(cls, lookup_specialized_type(cls, status)):
            raise ValueError(f"{cls} is not valid for lifecycle {status}")

        fixed_inputs = {fi.name: fi.value for fi in db_product.fixed_inputs}

        if new_root:
            name, product_block = new_root
            instances = {name: product_block}
        else:
            # TODO test using cls._load_root_instances() here as well
            instances = cls._load_instances(subscription.instances, status, match_domain_attr=False)  # type:ignore

        try:
            model = cls(
                product=product,
                customer_id=subscription.customer_id,
                subscription_id=subscription.subscription_id,
                description=subscription.description,
                status=status,
                insync=subscription.insync,
                start_date=subscription.start_date,
                end_date=subscription.end_date,
                note=subscription.note,
                version=subscription.version,
                **fixed_inputs,
                **instances,
            )
            model.db_model = subscription
            return model
        except ValidationError:
            logger.exception(
                "Subscription is not correct in database", loaded_fixed_inputs=fixed_inputs, loaded_instances=instances
            )
            raise

    @classmethod
    def from_subscription(cls: type[S], subscription_id: UUID | UUIDstr) -> S:
        """Use a subscription_id to return required fields of an existing subscription."""
        from orchestrator.domain.context_cache import get_from_cache, store_in_cache

        if cached_model := get_from_cache(subscription_id):
            return cast(S, cached_model)

        if not (subscription := cls._get_subscription(subscription_id)):
            raise ValueError(f"Subscription with id: {subscription_id}, does not exist")
        product = cls._to_product_model(subscription.product)

        status = SubscriptionLifecycle(subscription.status)

        if not cls.__base_type__:
            # Import here to prevent cyclic imports
            from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY

            try:
                cls = SUBSCRIPTION_MODEL_REGISTRY[subscription.product.name]  # type:ignore
            except KeyError:
                raise ProductNotInRegistryError(
                    f"'{subscription.product.name}' is not found within the SUBSCRIPTION_MODEL_REGISTRY"
                )
            cls = lookup_specialized_type(cls, status)
        elif not issubclass(cls, lookup_specialized_type(cls, status)):
            raise ValueError(f"{cls} is not valid for lifecycle {status}")

        fixed_inputs = {fi.name: fi.value for fi in subscription.product.fixed_inputs}

        instances = cls._load_root_instances(subscription_id)

        try:
            model = cls(
                product=product,
                customer_id=subscription.customer_id,
                subscription_id=subscription.subscription_id,
                description=subscription.description,
                status=status,
                insync=subscription.insync,
                start_date=subscription.start_date,
                end_date=subscription.end_date,
                note=subscription.note,
                version=subscription.version,
                **fixed_inputs,
                **instances,
            )
            model.db_model = subscription

            store_in_cache(model)

            return model
        except ValidationError:
            logger.exception(
                "Subscription is not correct in database", loaded_fixed_inputs=fixed_inputs, loaded_instances=instances
            )
            raise

    def save(self) -> None:
        """Save the subscription to the database."""
        specialized_type = lookup_specialized_type(self.__class__, self.status)
        if specialized_type and not isinstance(self, specialized_type):
            raise ValueError(
                f"Lifecycle status {self.status.value} requires specialized type {specialized_type!r}, was: {type(self)!r}"
            )

        existing_sub = db.session.get(
            SubscriptionTable,
            self.subscription_id,
            options=[
                selectinload(SubscriptionTable.instances)
                .joinedload(SubscriptionInstanceTable.product_block)
                .selectinload(ProductBlockTable.resource_types),
                selectinload(SubscriptionTable.instances).selectinload(SubscriptionInstanceTable.values),
            ],
        )
        if not (sub := (existing_sub or self.db_model)):
            raise ValueError("Cannot save SubscriptionModel without a db_model")

        # Make sure we refresh the object and not use an already mapped object
        db.session.refresh(sub)

        self.db_model = sub
        sub.product_id = self.product.product_id
        sub.customer_id = self.customer_id
        sub.description = self.description
        sub.status = self.status.value
        sub.insync = self.insync
        sub.start_date = self.start_date
        sub.end_date = self.end_date
        sub.note = self.note

        db.session.add(sub)
        db.session.flush()  # Sends INSERT and returns subscription_id without committing transaction

        old_instances_dict = {instance.subscription_instance_id: instance for instance in sub.instances}

        saved_instances, depends_on_instances = self._save_instances(self.subscription_id, self.status)

        for instances in depends_on_instances.values():
            for instance in instances:
                if instance.subscription_id != self.subscription_id:
                    raise ValueError(
                        "Attempting to save a Foreign `Subscription Instance` directly below a subscription. "
                        "This is not allowed."
                    )
        sub.instances = saved_instances

        # Calculate what to remove
        instances_set = {instance.subscription_instance_id for instance in sub.instances}
        for instance_id in instances_set:
            old_instances_dict.pop(instance_id, None)

        # What's left should be removed
        for instance in old_instances_dict.values():
            db.session.delete(instance)

        db.session.flush()

    @property
    def db_model(self) -> SubscriptionTable | None:
        if not self._db_model:
            self._db_model = self._get_subscription(self.subscription_id)
        return self._db_model

    @db_model.setter
    def db_model(self, value: SubscriptionTable) -> None:
        self._db_model = value


def validate_base_model(
    name: str, cls: type[Any], base_model: type[BaseModel] = DomainModel, errors: list[str] | None = None
) -> None:
    """Validates that the given class is not Pydantic BaseModel or its direct subclass."""
    # Instantiate errors list if not provided and avoid mutating default
    if errors is None:
        errors = []
    # Return early when the node is not a class as there is nothing to be done
    if not isclass(cls):
        return
    # Validate each field in the ProductBlockModel's field dictionaries
    if issubclass(cls, ProductBlockModel) or issubclass(cls, SubscriptionModel):
        for name, clz in cls._product_block_fields_.items():
            validate_base_model(name, clz, ProductBlockModel, errors)
        for name, clz in cls._non_product_block_fields_.items():
            validate_base_model(name, clz, SubscriptionModel, errors)
    # Generate error if node is Pydantic BaseModel or direct subclass
    if issubclass(cls, BaseModel):
        err_msg: str = (
            f"If this field was intended to be a {base_model.__name__}, define {name}:{cls.__name__} with "
            f"{base_model.__name__} as its superclass instead. e.g., class {cls.__name__}({base_model.__name__}):"
        )
        if cls is BaseModel:
            errors.append(f"Field {name}: {cls.__name__} can not be {BaseModel.__name__}. " + err_msg)
        if len(cls.__mro__) > 1 and cls.__mro__[1] is BaseModel:
            errors.append(
                f"Field {name}: {cls.__name__} can not be a direct subclass of {BaseModel.__name__}. " + err_msg
            )
    # Format all errors as one per line and raise a TypeError when they exist
    if errors:
        raise TypeError("\n".join(errors))


class SubscriptionModelRegistry(dict[str, type[SubscriptionModel]]):
    """A registry for all subscription models."""

    def __setitem__(self, __key: str, __value: type[SubscriptionModel]) -> None:
        """Set value for key in while validating against Pydantic BaseModel."""
        validate_base_model(__key, __value)
        super().__setitem__(__key, __value)

    def update(
        self,
        m: Any = None,
        /,
        **kwargs: type[SubscriptionModel],
    ) -> None:
        """Update dictionary with mapping and/or kwargs using `__setitem__`."""
        if m:
            if isinstance(m, Mapping):
                for key, value in m.items():
                    self[key] = value
            elif isinstance(m, Iterable):
                for index, item in enumerate(m):
                    try:
                        key, value = item
                    except ValueError:
                        raise TypeError(f"dictionary update sequence element #{index} is not an iterable of length 2")
                    self[key] = value
        for key, value in kwargs.items():
            self[key] = value


def _validate_lifecycle_change_for_product_block(
    used_by: SubscriptionInstanceTable,
    product_block_model: ProductBlockModel,
    status: SubscriptionLifecycle,
    description: str,
) -> None:
    """Validate if a lifecycle change for a single product model is possible."""

    logger.debug(
        "Checking the parent relations",
        parent_status=used_by.subscription.status,
        parent_description=used_by.subscription.description,
        self_status=status,
        self_description=description,
    )
    if (
        used_by.subscription != product_block_model.subscription
        and used_by.subscription.status not in SAFE_USED_BY_TRANSITIONS_FOR_STATUS[status]
    ):
        raise ValueError(
            f"Unsafe status change of Subscription with depending subscriptions: "
            f"{list(map(lambda instance: description, product_block_model.in_use_by))}"
        )


def validate_lifecycle_change(
    other: "SubscriptionModel",
    status: SubscriptionLifecycle,
) -> None:
    """Validate if a lifecycle change for a subscription model is possible.

    It will traverse all product blocks and check the `in_use_by` status to ensure that the lifecycle change
    is allowed.

    Note: A `ValueError` will be raised when a unsafe status change is found
    """
    for product_block_field, product_block_field_type in other._product_block_fields_.items():
        product_block_models = getattr(other, product_block_field)
        if is_list_type(product_block_field_type):
            for product_block_model in product_block_models:
                used_by_generator = (used_by for used_by in product_block_model.in_use_by if used_by)
                for used_by in used_by_generator:
                    _validate_lifecycle_change_for_product_block(
                        used_by, product_block_model, status, other.description
                    )
        elif (
            is_optional_type(product_block_field_type) or is_union_type(product_block_field_type)
        ) and product_block_models is None:
            pass
        else:
            used_by_generator = (used_by for used_by in product_block_models.in_use_by if used_by)
            for used_by in used_by_generator:
                _validate_lifecycle_change_for_product_block(used_by, product_block_models, status, other.description)

    logger.info(
        "Lifecycle validation check ok",
        subscription_id=other.subscription_id,
        subscription_description=other.description,
        status=status,
    )
