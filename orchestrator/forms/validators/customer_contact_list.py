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
from typing import Annotated, Generator, Optional, TypeVar
from uuid import UUID

from deprecated import deprecated
from pydantic import BeforeValidator, Field, conlist

from pydantic_forms.validators.components.contact_person import ContactPerson
from pydantic_forms.validators.helpers import remove_empty_items

T = TypeVar("T")  # pragma: no mutate


def customer_contact_list(
    customer: Optional[UUID] = None,
    customer_key: Optional[str] = "customer",
    min_items: Optional[int] = None,
    max_items: Optional[int] = None,
) -> type[list[T]]:
    def json_schema_extra() -> Generator:
        if customer:
            yield "customerId", customer
        if customer_key:
            yield "customerKey", customer_key

    return Annotated[  # type: ignore
        conlist(ContactPerson, min_length=min_items, max_length=max_items),
        BeforeValidator(remove_empty_items),
        Field(json_schema_extra=dict(json_schema_extra())),
    ]


@deprecated("Changed to 'customer_contact_list' with customerId and customerKey")
def organisation_contact_list(
    organisation: Optional[UUID] = None,
    organisation_key: Optional[str] = "organisation",
    min_items: Optional[int] = None,
    max_items: Optional[int] = None,
) -> type[list[T]]:
    def json_schema_extra() -> Generator:
        if organisation:
            yield "organisationId", organisation
        if organisation_key:
            yield "organisationKey", organisation_key

    return Annotated[  # type: ignore
        conlist(ContactPerson, min_length=min_items, max_length=max_items),
        BeforeValidator(remove_empty_items),
        Field(json_schema_extra=dict(json_schema_extra())),
    ]
