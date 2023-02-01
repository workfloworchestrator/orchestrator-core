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

from types import new_class
from typing import Any, ClassVar, Dict, Generator, List, Optional, Sequence, Type, TypeVar, get_args
from uuid import UUID

import structlog
from pydantic import BaseModel, ConstrainedList, EmailStr
from pydantic.errors import EnumMemberError
from pydantic.fields import ModelField
from pydantic.utils import update_not_none
from pydantic.validators import str_validator, uuid_validator

from orchestrator.forms import DisplayOnlyFieldType
from orchestrator.services import products
from orchestrator.types import AcceptData, SummaryData, strEnum

logger = structlog.get_logger(__name__)


T = TypeVar("T")  # pragma: no mutate


class UniqueConstrainedList(ConstrainedList, List[T]):
    unique_items: Optional[bool] = None

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        super().__modify_schema__(field_schema)
        update_not_none(field_schema, uniqueItems=cls.unique_items)

    @classmethod
    def __get_validators__(cls) -> Generator:  # noqa: B902
        yield from super().__get_validators__()
        if cls.unique_items is not None:
            yield cls.check_unique

    @classmethod
    def check_unique(cls, v: List[T]) -> List[T]:
        if len(set(v)) != len(v):
            raise ValueError("Items must be unique")

        return v

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        # Copy generic argument (T) if not set explicitly
        # This makes a lot of assuptions about the internals of `typing`
        if "__orig_bases__" in cls.__dict__ and cls.__dict__["__orig_bases__"]:
            generic_base_cls = cls.__dict__["__orig_bases__"][0]
            if (not hasattr(cls, "item_type") or isinstance(cls.item_type, TypeVar)) and get_args(generic_base_cls):
                cls.item_type = get_args(generic_base_cls)[0]

        # Make sure __args__ is set
        assert hasattr(cls, "item_type"), "Missing a concrete value for generic type argument"  # noqa: S101

        cls.__args__ = (cls.item_type,)

    def __class_getitem__(cls, key: Any) -> Any:
        # Some magic to make sure that subclasses of this class still work as expected
        class Inst(cls):  # type: ignore
            item_type = key
            __args__ = (key,)

        return Inst


def unique_conlist(
    item_type: Type[T],
    *,
    min_items: Optional[int] = None,
    max_items: Optional[int] = None,
    unique_items: Optional[bool] = None,
) -> Type[List[T]]:
    namespace = {
        "min_items": min_items,
        "max_items": max_items,
        "unique_items": unique_items,
        "__origin__": list,  # Needed for pydantic to detect that this is a list
        "__args__": (item_type,),  # Needed for pydantic to detect the item type
    }
    # We use new_class to be able to deal with Generic types
    return new_class(
        "ConstrainedListValue", (UniqueConstrainedList[item_type],), {}, lambda ns: ns.update(namespace)  # type:ignore
    )


def remove_empty_items(v: list) -> list:
    """Remove Falsy values from list.

    Sees dicts with all Falsy values as Falsy.
    This is used to allow people to submit list fields which are "empty" but are not really empty like:
    `[{}, None, {name:"", email:""}]`

    Example:
        >>> remove_empty_items([{}, None, [], {"a":""}])
        []
    """
    if v:
        return list(filter(lambda i: bool(i) and (not isinstance(i, dict) or any(i.values())), v))
    return v


class Accept(str):
    data: ClassVar[Optional[AcceptData]] = None

    class Values(strEnum):
        ACCEPTED = "ACCEPTED"
        INCOMPLETE = "INCOMPLETE"

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(
            format="accept",
            type="string",
            enum=[v.value for v in cls.Values],
            **({"data": cls.data} if cls.data else {}),
        )

    @classmethod
    def __get_validators__(cls) -> Generator:
        yield cls.enum_validator
        yield cls.must_be_complete

    @classmethod
    def enum_validator(cls, v: Any, field: "ModelField") -> str:
        try:
            enum_v = cls.Values(v)
        except ValueError:
            # cls.Values should be an enum, so will be iterable
            raise EnumMemberError(enum_values=list(cls.Values))
        return enum_v.value

    @classmethod
    def must_be_complete(cls, v: str) -> bool:
        if v == "INCOMPLETE":
            raise ValueError("Not all tasks are done")

        return v == "ACCEPTED"


class Choice(strEnum):
    label: ClassVar[str]

    def __new__(cls, value: str, label: Optional[str] = None) -> "Choice":
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label = label or value  # type:ignore
        return obj

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        kwargs = {}

        options = dict(map(lambda i: (i.value, i.label), cls.__members__.values()))

        if not all(map(lambda o: o[0] == o[1], options.items())):
            kwargs["options"] = options

        field_schema.update(type="string", **kwargs)


class ChoiceList(UniqueConstrainedList[T]):
    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        super().__modify_schema__(field_schema)

        data: dict = {}
        cls.item_type.__modify_schema__(data)  # type: ignore
        field_schema.update(**{k: v for k, v in data.items() if k == "options"})


def choice_list(
    item_type: Type[Choice],
    *,
    min_items: Optional[int] = None,
    max_items: Optional[int] = None,
    unique_items: Optional[bool] = None,
) -> Type[List[T]]:
    namespace = {
        "min_items": min_items,
        "max_items": max_items,
        "unique_items": unique_items,
        "__origin__": list,  # Needed for pydantic to detect that this is a list
        "item_type": item_type,  # Needed for pydantic to detect the item type
        "__args__": (item_type,),  # Needed for pydantic to detect the item type
    }
    # We use new_class to be able to deal with Generic types
    return new_class(
        "ChoiceListValue", (ChoiceList[item_type],), {}, lambda ns: ns.update(namespace)  # type:ignore
    )


class ContactPersonName(str):
    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(format="contactPersonName")


class ContactPerson(BaseModel):
    name: ContactPersonName
    email: EmailStr
    phone: str = ""


class ContactPersonList(ConstrainedList):
    item_type = ContactPerson
    __args__ = (ContactPerson,)

    organisation: ClassVar[Optional[UUID]] = None
    organisation_key: ClassVar[Optional[str]] = "organisation"

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        super().__modify_schema__(field_schema)
        data = {}

        if cls.organisation:
            data["organisationId"] = str(cls.organisation)
        if cls.organisation_key:
            data["organisationKey"] = cls.organisation_key

        field_schema.update(**data)

    @classmethod
    def __get_validators__(cls) -> Generator:
        yield from super().__get_validators__()
        yield remove_empty_items

    # TODO: Validatie organisation?


def contact_person_list(
    organisation: Optional[UUID] = None, organisation_key: Optional[str] = "organisation"
) -> Type[List[T]]:
    namespace = {"organisation": organisation, "organisation_key": organisation_key}
    # We use new_class to be able to deal with Generic types
    return new_class("ContactPersonListValue", (ContactPersonList,), {}, lambda ns: ns.update(namespace))


class LongText(str):
    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(format="long", type="string")

    @classmethod
    def __get_validators__(cls) -> Generator:
        yield str_validator


class DisplaySubscription(DisplayOnlyFieldType):
    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(format="subscription", type="string")


class Label(DisplayOnlyFieldType):
    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(format="label", type="string")


class Divider(DisplayOnlyFieldType):
    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(format="divider", type="string")


class OrganisationId(UUID):
    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(format="organisationId")

    @classmethod
    def __get_validators__(cls) -> Generator:
        yield uuid_validator

        # TODO: Check if org exists?


class ProductIdError(EnumMemberError):
    code = "product_id"
    enum_values: Sequence[Any]  # Required kwarg

    def __str__(self) -> str:
        permitted = ", ".join(repr(v) for v in self.enum_values)
        return f"value is not a valid enumeration member; permitted: {permitted}"


class ProductId(UUID):
    products: Optional[List[UUID]] = None

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        kwargs = {"uniforms": {"productIds": cls.products}} if cls.products else {}
        field_schema.update(format="productId", **kwargs)

    @classmethod
    def __get_validators__(cls) -> Generator:
        yield uuid_validator
        yield cls.is_product
        if cls.products:
            yield cls.in_products

    @classmethod
    def is_product(cls, v: UUID) -> UUID:
        product = products.get_product_by_id(v)
        if product is None:
            raise ValueError("Product not found")

        return v

    @classmethod
    def in_products(cls, v: UUID) -> UUID:
        if cls.products and v not in cls.products:
            raise ProductIdError(enum_values=list(map(str, cls.products)))

        return v


def product_id(products: Optional[List[UUID]] = None) -> Type[ProductId]:
    namespace = {"products": products}
    return new_class("ProductIdSpecific", (ProductId,), {}, lambda ns: ns.update(namespace))


class MigrationSummary(DisplayOnlyFieldType):
    data: ClassVar[Optional[SummaryData]] = None

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(format="summary", type="string", uniforms={"data": cls.data})


def migration_summary(data: Optional[SummaryData] = None) -> Type[MigrationSummary]:
    namespace = {"data": data}
    return new_class("MigrationSummaryValue", (MigrationSummary,), {}, lambda ns: ns.update(namespace))


class ListOfOne(UniqueConstrainedList[T]):
    min_items = 1
    max_items = 1


class ListOfTwo(UniqueConstrainedList[T]):
    min_items = 2
    max_items = 2
