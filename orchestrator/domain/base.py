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
from collections import defaultdict
from datetime import datetime
from itertools import groupby, zip_longest
from operator import attrgetter
from sys import version_info
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union
from uuid import UUID, uuid4

import structlog
from more_itertools import first, flatten, one, only
from pydantic import BaseModel, Field, ValidationError
from pydantic.fields import PrivateAttr
from pydantic.main import ModelMetaclass
from pydantic.types import ConstrainedList
from pydantic.typing import get_args, get_origin
from sqlalchemy.orm import selectinload

from orchestrator.db import (
    ProductBlockTable,
    ProductTable,
    SubscriptionInstanceRelationTable,
    SubscriptionInstanceTable,
    SubscriptionInstanceValueTable,
    SubscriptionTable,
    db,
)
from orchestrator.domain.lifecycle import ProductLifecycle, lookup_specialized_type, register_specialized_type
from orchestrator.types import (
    SAFE_PARENT_TRANSITIONS_FOR_STATUS,
    State,
    SubscriptionLifecycle,
    UUIDstr,
    is_list_type,
    is_of_type,
    is_optional_type,
    is_union_type,
)
from orchestrator.utils.datetime import nowtz
from orchestrator.utils.docs import make_product_block_docstring, make_subscription_model_docstring

logger = structlog.get_logger(__name__)


def _is_constrained_list_type(type: Type) -> bool:
    """Check if type is a constained list type.

    Example:
        >>> _is_constrained_list_type(List[int])
        False
        >>> class ListType(ConstrainedList):
        ...     min_items = 1
        >>> _is_constrained_list_type(ListType)
        True

    """
    # subclass on typing.List throws exception and there is no good way to test for this
    try:
        is_constrained_list = issubclass(type, ConstrainedList)
    except Exception:

        # Strip generic arguments, it still might be a subclass
        if get_origin(type):
            return _is_constrained_list_type(get_origin(type))  # type: ignore
        else:
            return False

    return is_constrained_list


T = TypeVar("T")  # pragma: no mutate
S = TypeVar("S", bound="SubscriptionModel")  # pragma: no mutate
B = TypeVar("B", bound="ProductBlockModel")  # pragma: no mutate


class DomainModel(BaseModel):
    """Base class for domain models.

    Contains all common Product block/Subscription instance code
    """

    class Config:
        validate_assignment = True  # pragma: no mutate
        validate_all = True  # pragma: no mutate
        arbitrary_types_allowed = True  # pragma: no mutate

    __base_type__: ClassVar[Optional[Type["DomainModel"]]] = None  # pragma: no mutate
    _product_block_fields_: ClassVar[Dict[str, Type]]
    _non_product_block_fields_: ClassVar[Dict[str, Type]]

    def __init_subclass__(
        cls, *args: Any, lifecycle: Optional[List[SubscriptionLifecycle]] = None, **kwargs: Any
    ) -> None:
        super().__init_subclass__()
        cls._find_special_fields()

        if kwargs.keys():
            logger.warning(
                "Unexpected keyword arguments in domain model class",  # pragma: no mutate
                class_name=cls.__name__,
                kwargs=kwargs.keys(),
            )

        # Check if child subscription instance models conform to the same lifecycle
        for product_block_field_name, product_block_field_type in cls._get_child_product_block_types().items():
            if lifecycle:
                for lifecycle_status in lifecycle:
                    if isinstance(product_block_field_type, tuple):
                        for field_type in product_block_field_type:
                            specialized_type = lookup_specialized_type(field_type, lifecycle_status)
                            if not issubclass(field_type, specialized_type):
                                raise AssertionError(
                                    f"The lifecycle status of the type for the field: {product_block_field_name}, {specialized_type.__name__} (based on {field_type.__name__}) is not suitable for the lifecycle status ({lifecycle_status}) of this model"
                                )
                    else:
                        specialized_type = lookup_specialized_type(product_block_field_type, lifecycle_status)
                        if not issubclass(product_block_field_type, specialized_type):
                            raise AssertionError(
                                f"The lifecycle status of the type for the field: {product_block_field_name}, {specialized_type.__name__} (based on {product_block_field_type.__name__}) is not suitable for the lifecycle status ({lifecycle_status}) of this model"
                            )

    @classmethod
    def _get_child_product_block_types(
        cls,
    ) -> Dict[str, Union[Type["ProductBlockModel"], Tuple[Type["ProductBlockModel"]]]]:
        """Return all the product block model types.

        This strips any List[..] or Optional[...] types.
        """
        result = {}
        for product_block_field_name, product_block_field_type in cls._product_block_fields_.items():
            if is_union_type(product_block_field_type) and not is_optional_type(product_block_field_type):
                field_type: Union[Type["ProductBlockModel"], Tuple[Type["ProductBlockModel"]]] = get_args(product_block_field_type)  # type: ignore
            elif is_list_type(product_block_field_type) or is_optional_type(product_block_field_type):
                field_type = first(get_args(product_block_field_type))
            else:
                field_type = product_block_field_type

            result[product_block_field_name] = field_type
        return result

    @classmethod
    def _find_special_fields(cls: Type) -> None:
        """Make and store a list of resource_type fields and product block fields."""
        cls._non_product_block_fields_ = {}
        cls._product_block_fields_ = {}

        if version_info.minor < 10:
            annotations = cls.__dict__.get("__annotations__", {})
        else:
            if TYPE_CHECKING:
                annotations = {}
            else:
                # Only available in python > 3.10
                from inspect import get_annotations

                annotations = get_annotations(cls)

        for field_name, field_type in annotations.items():
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

            # We only want fields that are on this class and not on the parent
            if is_product_block_field:
                cls._product_block_fields_[field_name] = field_type
            else:
                cls._non_product_block_fields_[field_name] = field_type

    @classmethod
    def _init_instances(
        cls, subscription_id: UUID, skip_keys: Optional[List[str]] = None
    ) -> Dict[str, Union[List["ProductBlockModel"], "ProductBlockModel"]]:
        """Initialize default subscription instances.

        When a new domain model is created that is not loaded from an existing subscription.
        We also create all subscription instances for it. This function does that.

        Args:
            skip_keys: list of fields on the class to skip when creating dummy instances.

        Returns:
            A dict with instances to pass to the new model

        """
        if skip_keys is None:
            skip_keys = []

        instances: Dict[str, Union[List[ProductBlockModel], ProductBlockModel]] = {}
        for product_block_field_name, product_block_field_type in cls._product_block_fields_.items():
            if product_block_field_name in skip_keys:
                continue

            if is_list_type(product_block_field_type):
                if _is_constrained_list_type(product_block_field_type):
                    product_block_model = one(get_args(product_block_field_type))
                    default_value = product_block_field_type()
                    # if constrainedlist has minimum, return that minimum else empty list
                    if product_block_field_type.min_items:
                        logger.debug("creating min_items", type=product_block_field_type)  # pragma: no mutate
                        for _ in range(product_block_field_type.min_items):
                            default_value.append(product_block_model.new(subscription_id=subscription_id))
                else:
                    # a list field of ProductBlockModels without limits gets an empty list
                    default_value = []
            elif is_optional_type(product_block_field_type, ProductBlockModel):
                default_value = None
            elif is_union_type(product_block_field_type):
                raise ValueError(
                    "Union Types must always be `Optional` when calling `.new().` We are unable to detect which type to intialise and Union types always cross subscription boundaries."
                )
            else:
                product_block_model = product_block_field_type
                # Scalar field of a ProductBlockModel expects 1 instance
                default_value = product_block_model.new(subscription_id=subscription_id)
            instances[product_block_field_name] = default_value
        return instances

    @classmethod
    def _load_instances(
        cls,
        db_instances: List[SubscriptionInstanceTable],
        status: SubscriptionLifecycle,
        match_domain_attr: bool = True,
    ) -> Dict[str, Union[Optional["ProductBlockModel"], List["ProductBlockModel"]]]:
        """Load subscription instances for this domain model.

        When a new domain model is loaded from an existing subscription we also load all
        subscription instances for it. This function does that.

        Args:
            db_instances: list of database models to load from
            status: SubscriptionLifecycle of subscription to check if models match
            match_domain_attr: Match domain attribute from relation (not wanted when loading product blocks directly related to subscriptions)

        Returns:
            A dict with instances to pass to the new model

        """

        instances: Dict[str, Union[Optional[ProductBlockModel], List[ProductBlockModel]]] = {}

        def keyfunc(i: SubscriptionInstanceTable) -> str:
            return i.product_block.name

        sorted_instances = sorted(db_instances, key=keyfunc)
        grouped_instances = {k: list(g) for k, g in groupby(sorted_instances, keyfunc)}

        def match_domain_model_attr_if_possible(field_name: str) -> Callable:
            def domain_filter(instance: SubscriptionInstanceTable) -> bool:
                """
                Match domain model attributes.

                This helper is necessary to filter through all relations in a subscription. Not all subscriptions have a
                domain model attribute that is set as it is not always necessary. However when it is set, it is necessary
                to filter through instances depending on that attribute.

                Args:
                    instance: child instance

                Returns:
                    Boolean of match.

                """
                # We don't match on the product_blocks directly under subscriptions. They don't have parent relations to those
                if not match_domain_attr:
                    return True

                attr_names = {
                    relation.domain_model_attr for relation in instance.parent_relations if relation.domain_model_attr
                }

                # We can assume true is no domain_model_attr is set.
                return not attr_names or field_name in attr_names

            return domain_filter

        for product_block_field_name, product_block_field_type in cls._product_block_fields_.items():
            filter_func = match_domain_model_attr_if_possible(product_block_field_name)
            if is_list_type(product_block_field_type):
                if product_block_field_name not in grouped_instances:
                    if _is_constrained_list_type(product_block_field_type):
                        product_block_model_list = product_block_field_type()
                    else:
                        product_block_model_list = []

                product_block_model = one(get_args(product_block_field_type))
                instance_list: List[SubscriptionInstanceTable] = list(
                    filter(
                        filter_func, flatten(grouped_instances.get(name, []) for name in product_block_model.__names__)
                    )
                )
                product_block_model_list.extend(
                    product_block_model.from_db(subscription_instance=instance, status=status)
                    for instance in instance_list
                )

                instances[product_block_field_name] = product_block_model_list
            elif is_union_type(product_block_field_type) and not is_optional_type(product_block_field_type):
                instance = only(
                    list(
                        filter(
                            filter_func,
                            flatten(
                                grouped_instances.get(field_type.name, [])
                                for field_type in get_args(product_block_field_type)
                            ),
                        )
                    )
                )
                product_block_model = None

                if instance is None:
                    raise ValueError("Required subscription instance is missing in the database")

                for field_type in get_args(product_block_field_type):
                    if instance.product_block.name == field_type.name:
                        product_block_model = field_type

                assert (  # noqa: S101
                    product_block_model is not None
                ), "Product block model has not been resolved. Unable to continue"
                instances[product_block_field_name] = product_block_model.from_db(
                    subscription_instance=instance, status=status
                )

            else:
                product_block_model = product_block_field_type
                if is_optional_type(product_block_field_type):
                    product_block_model = first(get_args(product_block_model))

                instance = only(
                    list(
                        filter(
                            filter_func,
                            flatten(grouped_instances.get(name, []) for name in product_block_model.__names__),
                        )
                    )
                )

                if is_optional_type(product_block_field_type) and instance is None:
                    instances[product_block_field_name] = None
                elif not is_optional_type(product_block_field_type) and instance is None:
                    raise ValueError("Required subscription instance is missing in database")
                else:
                    instances[product_block_field_name] = product_block_model.from_db(
                        subscription_instance=instance, status=status
                    )

        return instances

    @classmethod
    def _data_from_lifecycle(cls, other: "DomainModel", status: SubscriptionLifecycle, subscription_id: UUID) -> Dict:
        data = other.dict()

        for field_name, field_type in cls._product_block_fields_.items():
            if is_list_type(field_type):
                data[field_name] = []
                for item in getattr(other, field_name):
                    data[field_name].append(
                        one(get_args(field_type))._from_other_lifecycle(item, status, subscription_id)
                    )
            else:
                value = getattr(other, field_name)
                if is_optional_type(field_type):
                    field_type = first(get_args(field_type))
                    if value:
                        data[field_name] = field_type._from_other_lifecycle(value, status, subscription_id)
                    else:
                        data[field_name] = None

                elif is_union_type(field_type) and not is_optional_type(field_type):
                    field_types = get_args(field_type)
                    for f_type in field_types:
                        if f_type.name == value.name:
                            field_type = f_type
                    data[field_name] = field_type._from_other_lifecycle(value, status, subscription_id)
                else:
                    data[field_name] = field_type._from_other_lifecycle(value, status, subscription_id)
        return data

    def _save_instances(
        self, subscription_id: UUID, status: SubscriptionLifecycle
    ) -> Tuple[List[SubscriptionInstanceTable], Dict[str, List[SubscriptionInstanceTable]]]:
        """Save subscription instances for this domain model.

        When a domain model is saved to the database we need to save all child subscription instances for it.

        Args:
            subscription_id: The subscription id
            status: SubscriptionLifecycle of subscription to check if models match

        Returns:
            A list with instances which are saved and a dict with direct children

        """
        saved_instances: List[SubscriptionInstanceTable] = []
        child_instances: Dict[str, List[SubscriptionInstanceTable]] = {}
        for product_block_field, product_block_field_type in self._product_block_fields_.items():
            product_block_models = getattr(self, product_block_field)
            if is_list_type(product_block_field_type):
                field_instance_list = []
                for product_block_model in product_block_models:
                    saved, child = product_block_model.save(subscription_id=subscription_id, status=status)
                    field_instance_list.append(child)
                    saved_instances.extend(saved)
                child_instances[product_block_field] = field_instance_list
            elif (
                is_optional_type(product_block_field_type) or is_union_type(product_block_field_type)
            ) and product_block_models is None:
                pass
            else:
                saved, child = product_block_models.save(subscription_id=subscription_id, status=status)
                child_instances[product_block_field] = [child]
                saved_instances.extend(saved)

        return saved_instances, child_instances


class ProductBlockModelMeta(ModelMetaclass):
    """Metaclass used to create product block instances.

    This metaclass is used to make sure the class contains product block metadata.

    This metaclass should not be used directly in the class definition. Instead a new product block model should inherit
    from ProductBlockModel which has this metaclass defined.

    You can find some examples in: :ref:`domain-models`
    """

    __names__: Set[str]
    name: Optional[str]
    product_block_id: UUID
    description: str
    tag: str
    registry: Dict[str, Type["ProductBlockModel"]] = {}  # pragma: no mutate

    def _fix_pb_data(self) -> None:
        if not self.name:
            raise ValueError(f"Cannot create instance of abstract class. Use one of {self.__names__}")

        # Would have been nice to do this in __init_subclass__ but that runs outside the app context so we cant access the db
        # So now we do it just before we instantiate the instance
        if not hasattr(self, "product_block_id"):
            product_block = ProductBlockTable.query.filter(ProductBlockTable.name == self.name).one()
            self.product_block_id = product_block.product_block_id
            self.description = product_block.description
            self.tag = product_block.tag

    def __call__(self, *args: Any, **kwargs: Any) -> B:
        self._fix_pb_data()

        kwargs["name"] = self.name

        return super().__call__(*args, **kwargs)


class ProductBlockModel(DomainModel, metaclass=ProductBlockModelMeta):
    r"""Base class for all product block models.

    This class should have been called SubscriptionInstanceModel.

    ProductTable Blocks are represented as dataclasses with pydantic runtime validation.

    Different stages of a subscription lifecycle could require different product block definition. Mainly to support
    mandatory fields when a subscription is active. To support this a lifecycle specific product block definition can
    be created by subclassing the generic product block with keyword argument 'lifecycle' and overriding its fields.

    All product blocks are related to a database ProductBlockTable object through the `product_block_name` that is given
    as class keyword argument.

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

    Create a new empty product block
    >>> example1 = BlockInactive()  # doctest:+SKIP

    Create a new instance based on a dict in the state:
    >>> example2 = BlockInactive(\*\*state)  # doctest:+SKIP

    To retrieve a ProductBlockModel from the database.:
    >>> BlockInactive.from_db(subscription_instance_id)  # doctest:+SKIP
    """

    registry: ClassVar[Dict[str, Type["ProductBlockModel"]]]  # pragma: no mutate
    __names__: ClassVar[Set[str]] = set()
    product_block_id: ClassVar[UUID]
    description: ClassVar[str]
    tag: ClassVar[str]
    _db_model: SubscriptionInstanceTable = PrivateAttr()

    # Product block name. This needs to be an instance var because its part of the API (we expose it to the frontend)
    # Is actually optional since abstract classes dont have it. In practice it is always set
    name: str
    subscription_instance_id: UUID
    owner_subscription_id: UUID
    label: Optional[str] = None

    def __init_subclass__(
        cls,
        *,
        product_block_name: Optional[str] = None,
        lifecycle: Optional[List[SubscriptionLifecycle]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init_subclass__(lifecycle=lifecycle, **kwargs)

        if product_block_name is not None:
            # This is a concrete product block base class (so not a abstract super class or a specific lifecycle version)
            cls.name = product_block_name
            cls.__base_type__ = cls
            cls.__names__ = {cls.name}
            ProductBlockModel.registry[cls.name] = cls
        elif lifecycle is None:
            # Abstract class, no product block name
            cls.name = None  # type:ignore
            cls.__names__ = set()

        # For everything except abstract classes
        if cls.name is not None:
            register_specialized_type(cls, lifecycle)

            # Add ourself to any super class. That way we can match a superclass to an instance when loading
            for klass in cls.__mro__:
                if issubclass(klass, ProductBlockModel):
                    klass.__names__.add(cls.name)

        cls.__doc__ = make_product_block_docstring(cls, lifecycle)

    @classmethod
    def diff_product_block_in_database(cls) -> Dict[str, Any]:
        """Return any differences between the attrs defined on the domain model and those on product blocks in the database.

        This is only needed to check if the domain model and database models match which would be done during testing...
        """
        if not cls.name:
            # This is a superclass we can't check that
            return {}

        product_block_db = ProductBlockTable.query.filter(ProductBlockTable.name == cls.name).one_or_none()

        product_blocks_in_db = {pb.name for pb in product_block_db.children} if product_block_db else set()
        product_blocks_types_in_model = cls._get_child_product_block_types().values()

        if product_blocks_types_in_model and isinstance(first(product_blocks_types_in_model), tuple):
            # There may only be one in the type if it is a Tuple
            product_blocks_in_model = set(flatten(map(attrgetter("__names__"), one(product_blocks_types_in_model))))  # type: ignore
        else:
            product_blocks_in_model = set(flatten(map(attrgetter("__names__"), product_blocks_types_in_model)))

        missing_product_blocks_in_db = product_blocks_in_model - product_blocks_in_db
        missing_product_blocks_in_model = product_blocks_in_db - product_blocks_in_model

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

        missing_data: Dict[str, Any] = {}
        if product_blocks_types_in_model and isinstance(first(product_blocks_types_in_model), tuple):
            for product_block_model in one(product_blocks_types_in_model):  # type: ignore
                missing_data.update(product_block_model.diff_product_block_in_database())
        else:
            for product_block_in_model in product_blocks_types_in_model:
                missing_data.update(product_block_in_model.diff_product_block_in_database())  # type: ignore

        diff = {
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
    def new(cls: Type[B], subscription_id: UUID, **kwargs: Any) -> B:
        """Create a new empty product block.

        We need to use this instead of the normal constructor because that assumes you pass in
        all required values. That is cumbersome since that means creating a tree of product blocks.

        This is similar to `from_product_id()`
        """
        sub_instances = cls._init_instances(subscription_id, list(kwargs.keys()))

        subscription_instance_id = uuid4()

        # Make sure product block stuff is already set if new is the first usage of this class
        cls._fix_pb_data()

        db_model = SubscriptionInstanceTable(
            product_block_id=cls.product_block_id,
            subscription_instance_id=subscription_instance_id,
            subscription_id=subscription_id,
        )
        db.session.enable_relationship_loading(db_model)
        model = cls(subscription_instance_id=subscription_instance_id, owner_subscription_id=subscription_id, **sub_instances, **kwargs)  # type: ignore
        model._db_model = db_model
        return model

    @classmethod
    def _load_instances_values(cls, instance_values: List[SubscriptionInstanceValueTable]) -> Dict[str, str]:
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

        for siv in instance_values:
            # check the type of the siv in the instance and act accordingly: only lists and scalar values supported
            resource_type_name = siv.resource_type.resource_type
            if resource_type_name in list_field_names:
                instance_values_dict[resource_type_name].append(siv.value)
            else:
                instance_values_dict[resource_type_name] = siv.value

        # Make sure values are sorted. This already happens when they come from the db.
        # However newly created SubscriptionInstances might not have the correct order
        for field_name in list_field_names:
            instance_values_dict[field_name] = sorted(instance_values_dict[field_name])

        return instance_values_dict

    @classmethod
    def _from_other_lifecycle(
        cls: Type[B],
        other: "ProductBlockModel",
        status: SubscriptionLifecycle,
        subscription_id: UUID,
    ) -> B:
        """Create new domain model from instance while changing the status.

        This makes sure we always have a specific instance..
        """
        if not cls.__base_type__:
            cls = ProductBlockModel.registry.get(other.name, cls)  # type:ignore
            cls = lookup_specialized_type(cls, status)

        data = cls._data_from_lifecycle(other, status, subscription_id)

        model = cls(**data)
        model._db_model = other._db_model
        return model

    @classmethod
    def from_db(
        cls: Type[B],
        subscription_instance_id: Optional[UUID] = None,
        subscription_instance: Optional[SubscriptionInstanceTable] = None,
        status: Optional[SubscriptionLifecycle] = None,
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
            subscription_instance = SubscriptionInstanceTable.query.get(subscription_instance_id)
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
        sub_instances = cls._load_instances(subscription_instance.children, status)

        try:
            model = cls(
                subscription_instance_id=subscription_instance_id,
                owner_subscription_id=subscription_instance.subscription_id,
                subscription=subscription_instance.subscription,
                label=label,
                **instance_values,  # type: ignore
                **sub_instances,  # type: ignore
            )
            model._db_model = subscription_instance
            return model
        except ValidationError:
            logger.exception(
                "Subscription is not correct in database",
                loaded_instance_values=instance_values,
                loaded_sub_instances=sub_instances,
            )
            raise

    def _save_instance_values(
        self, product_block: ProductBlockTable, current_values: List[SubscriptionInstanceValueTable]
    ) -> List[SubscriptionInstanceValueTable]:
        """Save non product block fields (instance values).

        Returns:
            List of database instances values to save

        """
        resource_types = {rt.resource_type: rt for rt in product_block.resource_types}
        current_values_dict: Dict[str, List[SubscriptionInstanceValueTable]] = defaultdict(list)
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
                    if val:
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
        subscription_instance_mapping: Dict[str, List[SubscriptionInstanceTable]],
    ) -> None:
        """
        Save the domain model attribute to the database.

        This function iterates through the subscription instances and stores the domain model attribute in the
        hierarchy relationship.

        Args:
            subscription_instance_mapping: a mapping of the domain model attribute a underlying instances

        Returns:
            None

        """
        children_relations = []
        # Set the domain_model_attrs in the database
        for domain_model_attr, instances in subscription_instance_mapping.items():
            instance: SubscriptionInstanceTable
            for index, instance in enumerate(instances):
                relation = SubscriptionInstanceRelationTable(
                    parent_id=subscription_instance.subscription_instance_id,
                    child_id=instance.subscription_instance_id,
                    order_id=index,
                    domain_model_attr=domain_model_attr,
                )
                children_relations.append(relation)
        subscription_instance.children_relations = children_relations

    def save(
        self,
        *,
        subscription_id: UUID,
        status: SubscriptionLifecycle,
    ) -> Tuple[List[SubscriptionInstanceTable], SubscriptionInstanceTable]:
        """Save the current model instance to the database.

        This means saving the whole tree of subscription instances and seperately saving all instance values for this instance.

        Args:
            status: current SubscriptionLifecycle to check if all constraints match
            subscription_id: Optional subscription id needed if this is a new model

        Returns:
            List of saved instances

        """
        if not self.name:
            raise ValueError(f"Cannot create instance of abstract class. Use one of {self.__names__}")

        # Make sure we have a valid subscription instance database model
        subscription_instance: SubscriptionInstanceTable = SubscriptionInstanceTable.query.get(
            self.subscription_instance_id
        )
        if subscription_instance:
            # Make sure we do not use a mapped session.
            db.session.refresh(subscription_instance)
            # Block unsafe status changes on domain models that have Subscription instances with parent relations
            for parent in subscription_instance.parents:
                if (
                    parent.subscription != self.subscription
                    and parent.subscription.status not in SAFE_PARENT_TRANSITIONS_FOR_STATUS[status]
                ):
                    raise ValueError(
                        f"Unsafe status change of Subscription with depending subscriptions: {list(map(lambda instance: instance.subscription.description, subscription_instance.parents))}"
                    )
            # If this is a "foreign" instance we just stop saving and return it so only its relation is saved
            # We should not touch these themselves
            if self.subscription and subscription_instance.subscription_id != subscription_id:
                return [], subscription_instance

            self._db_model = subscription_instance
        else:
            subscription_instance = self._db_model
            # We only need to add to the session if the subscription_instance does not exist.
            db.session.add(subscription_instance)

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

        sub_instances, children = self._save_instances(subscription_id, status)

        # Save the subscription instances relations.
        self._set_instance_domain_model_attrs(subscription_instance, children)

        return sub_instances + [subscription_instance], subscription_instance

    @property
    def subscription(self) -> SubscriptionTable:
        return self.db_model.subscription

    @property
    def db_model(self) -> SubscriptionInstanceTable:
        return self._db_model

    @property
    def parents(self) -> List[SubscriptionInstanceTable]:
        return self._db_model.parents

    @property
    def children(self) -> List[SubscriptionInstanceTable]:
        return self._db_model.children


class ProductModel(BaseModel):
    """Represent the product as defined in the database as a dataclass."""

    class Config:
        validate_assignment = True  # pragma: no mutate
        validate_all = True  # pragma: no mutate
        arbitrary_types_allowed = True  # pragma: no mutate

    product_id: UUID
    name: str
    description: str
    product_type: str
    tag: str
    status: ProductLifecycle


class SubscriptionModel(DomainModel):
    r"""Base class for all product subscription models.

    Define a subscription model:
    >>> class SubscriptionInactive(SubscriptionModel, product_type="SP"):  # doctest:+SKIP
    ...    block: Optional[ProductBlockModelInactive] = None

    >>> class Subscription(BlockInactive, lifecycle=[SubscriptionLifecycle.ACTIVE]):  # doctest:+SKIP
    ...    block: ProductBlockModel


    This example defines a subscription model with two different contraints based on lifecycle. `Subscription` is valid only for `ACTIVE`
    And `SubscriptionInactive` for all other states.
    `product_type` must be defined on the base class and need not to be defined on the others

    Create a new empty subscription
    >>> example1 = SubscriptionInactive.from_product_id(product_id, customer_id)  # doctest:+SKIP

    Create a new instance based on a dict in the state:
    >>> example2 = SubscriptionInactive(\*\*state)  # doctest:+SKIP

    To retrieve a ProductBlockModel from the database:
    >>> SubscriptionInactive.from_subscription(subscription_id)  # doctest:+SKIP
    """

    product: ProductModel
    customer_id: UUID
    _db_model: SubscriptionTable = PrivateAttr()
    subscription_id: UUID = Field(default_factory=uuid4)  # pragma: no mutate
    description: str = "Initial subscription"  # pragma: no mutate
    status: SubscriptionLifecycle = SubscriptionLifecycle.INITIAL  # pragma: no mutate
    insync: bool = False  # pragma: no mutate
    start_date: Optional[datetime] = None  # pragma: no mutate
    end_date: Optional[datetime] = None  # pragma: no mutate
    note: Optional[str] = None  # pragma: no mutate

    def __new__(cls, *args: Any, status: Optional[SubscriptionLifecycle] = None, **kwargs: Any) -> "SubscriptionModel":

        # status can be none if created during change_lifecycle
        if status and not issubclass(cls, lookup_specialized_type(cls, status)):
            raise ValueError(f"{cls} is not valid for status {status}")

        return super().__new__(cls)

    def __init_subclass__(
        cls, is_base: bool = False, lifecycle: Optional[List[SubscriptionLifecycle]] = None, **kwargs: Any
    ) -> None:
        super().__init_subclass__(lifecycle=lifecycle, **kwargs)

        if is_base:
            cls.__base_type__ = cls

        if is_base or lifecycle:
            register_specialized_type(cls, lifecycle)

        cls.__doc__ = make_subscription_model_docstring(cls, lifecycle)

    @classmethod
    def diff_product_in_database(cls, product_id: UUID) -> Dict[str, Any]:
        """Return any differences between the attrs defined on the domain model and those on product blocks in the database.

        This is only needed to check if the domain model and database models match which would be done during testing...
        """
        product_db = ProductTable.query.get(product_id)

        product_blocks_in_db = {pb.name for pb in product_db.product_blocks} if product_db else set()
        product_blocks_types_in_model = cls._get_child_product_block_types().values()
        if product_blocks_types_in_model and isinstance(first(product_blocks_types_in_model), tuple):
            product_blocks_in_model = set(flatten(map(attrgetter("__names__"), one(product_blocks_types_in_model))))  # type: ignore
        else:
            product_blocks_in_model = set(flatten(map(attrgetter("__names__"), product_blocks_types_in_model)))

        missing_product_blocks_in_db = product_blocks_in_model - product_blocks_in_db
        missing_product_blocks_in_model = product_blocks_in_db - product_blocks_in_model
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

        missing_data_children: Dict[str, Any] = {}
        for product_block_in_model in product_blocks_types_in_model:
            missing_data_children.update(product_block_in_model.diff_product_block_in_database())  # type: ignore

        diff = {
            k: v
            for k, v in {
                "missing_product_blocks_in_db": missing_product_blocks_in_db,
                "missing_product_blocks_in_model": missing_product_blocks_in_model,
                "missing_fixed_inputs_in_db": missing_fixed_inputs_in_db,
                "missing_fixed_inputs_in_model": missing_fixed_inputs_in_model,
                "missing_in_children": missing_data_children,
            }.items()
            if v
        }

        missing_data = {}
        if diff:
            missing_data[product_db.name] = diff

        return missing_data

    @classmethod
    def from_product_id(
        cls: Type[S],
        product_id: Union[UUID, UUIDstr],
        customer_id: Union[UUID, UUIDstr],
        status: SubscriptionLifecycle = SubscriptionLifecycle.INITIAL,
        description: Optional[str] = None,
        insync: bool = False,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        note: Optional[str] = None,
    ) -> S:
        """Use product_id (and customer_id) to return required fields of a new empty subscription."""
        # Caller wants a new instance and provided a product_id and customer_id
        product_db = ProductTable.query.get(product_id)
        product = ProductModel(
            product_id=product_db.product_id,
            name=product_db.name,
            description=product_db.description,
            product_type=product_db.product_type,
            tag=product_db.tag,
            status=product_db.status,
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
        )
        db.session.add(subscription)

        fixed_inputs = {fi.name: fi.value for fi in product_db.fixed_inputs}
        instances = cls._init_instances(subscription_id)

        if isinstance(customer_id, str):
            customer_id = UUID(customer_id)

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
            **fixed_inputs,
            **instances,  # type: ignore
        )
        model._db_model = subscription
        return model

    @classmethod
    def from_other_lifecycle(
        cls: Type[S],
        other: "SubscriptionModel",
        status: SubscriptionLifecycle,
    ) -> S:
        """Create new domain model from instance while changing the status.

        This makes sure we always have a speficic instance.
        """
        if not cls.__base_type__:
            # Import here to prevent cyclic imports
            from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY

            cls = SUBSCRIPTION_MODEL_REGISTRY.get(other.product.name, cls)  # type:ignore
            cls = lookup_specialized_type(cls, status)

        data = cls._data_from_lifecycle(other, status, other.subscription_id)

        data["status"] = status
        if data["start_date"] is None and status == SubscriptionLifecycle.ACTIVE:
            data["start_date"] = nowtz()
        if data["end_date"] is None and status == SubscriptionLifecycle.TERMINATED:
            data["end_date"] = nowtz()

        model = cls(**data)
        model._db_model = other._db_model

        return model

    @classmethod
    def from_subscription(cls: Type[S], subscription_id: Union[UUID, UUIDstr]) -> S:
        """Use a subscription_id to return required fields of an existing subscription."""
        subscription = SubscriptionTable.query.options(
            selectinload(SubscriptionTable.instances)
            .selectinload(SubscriptionInstanceTable.product_block)
            .selectinload(ProductBlockTable.resource_types),
            selectinload(SubscriptionTable.instances).selectinload(SubscriptionInstanceTable.parent_relations),
            selectinload(SubscriptionTable.instances).selectinload(SubscriptionInstanceTable.values),
        ).get(subscription_id)
        product = ProductModel(
            product_id=subscription.product.product_id,
            name=subscription.product.name,
            description=subscription.product.description,
            product_type=subscription.product.product_type,
            tag=subscription.product.tag,
            status=subscription.product.status,
        )
        status = SubscriptionLifecycle(subscription.status)

        if not cls.__base_type__:
            # Import here to prevent cyclic imports
            from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY

            cls = SUBSCRIPTION_MODEL_REGISTRY.get(subscription.product.name, cls)  # type:ignore
            cls = lookup_specialized_type(cls, status)
        elif not issubclass(cls, lookup_specialized_type(cls, status)):
            raise ValueError(f"{cls} is not valid for lifecycle {status}")

        fixed_inputs = {fi.name: fi.value for fi in subscription.product.fixed_inputs}
        instances = cls._load_instances(subscription.instances, status, match_domain_attr=False)

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
                **fixed_inputs,
                **instances,  # type: ignore
            )
            model._db_model = subscription
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

        sub = SubscriptionTable.query.options(
            selectinload(SubscriptionTable.instances)
            .selectinload(SubscriptionInstanceTable.product_block)
            .selectinload(ProductBlockTable.resource_types),
            selectinload(SubscriptionTable.instances).selectinload(SubscriptionInstanceTable.values),
        ).get(self.subscription_id)
        if not sub:
            sub = self._db_model

        # Make sure we refresh the object and not use an already mapped object
        db.session.refresh(sub)

        self._db_model = sub
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

        saved_instances, child_instances = self._save_instances(self.subscription_id, self.status)

        for instances in child_instances.values():
            for instance in instances:
                if instance.subscription_id != self.subscription_id:
                    raise ValueError(
                        "Attempting to save a Foreign `Subscription Instance` directly below a subscription. This is not allowed."
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
    def db_model(self) -> SubscriptionTable:
        return self._db_model


SI = TypeVar("SI")  # pragma: no mutate


class SubscriptionInstanceList(ConstrainedList, List[SI]):
    """Shorthand to create constrained lists of product blocks."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)  # type:ignore

        # Copy generic argument (SI) if not set explicitly
        # This makes a lot of assuptions about the internals of `typing`
        if "__orig_bases__" in cls.__dict__ and cls.__dict__["__orig_bases__"]:
            generic_base_cls = cls.__dict__["__orig_bases__"][0]
            if not hasattr(generic_base_cls, "item_type") and get_args(generic_base_cls):
                cls.item_type = get_args(generic_base_cls)[0]

        # Make sure __args__ is set
        cls.__args__ = (cls.item_type,)
