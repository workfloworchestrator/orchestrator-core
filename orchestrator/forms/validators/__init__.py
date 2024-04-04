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


from nwastdlib.vlans import VlanRanges
from orchestrator.forms.validators.customer_contact_list import customer_contact_list
from orchestrator.forms.validators.customer_id import CustomerId
from orchestrator.forms.validators.display_subscription import DisplaySubscription
from orchestrator.forms.validators.product_id import ProductId, ProductIdError, product_id
from pydantic_forms.types import strEnum
from pydantic_forms.validators import (
    Accept,
    Choice,
    ContactPerson,
    ContactPersonName,
    Divider,
    Label,
    ListOfOne,
    ListOfTwo,
    LongText,
    MigrationSummary,
    OrganisationId,
    Timestamp,
    choice_list,
    contact_person_list,
    migration_summary,
    timestamp,
    unique_conlist,
)
from pydantic_forms.validators.helpers import remove_empty_items

__all__ = [
    "Accept",
    "Choice",
    "choice_list",
    "ContactPerson",
    "ContactPersonName",
    "contact_person_list",
    "CustomerId",
    "DisplaySubscription",
    "Divider",
    "Label",
    "ListOfOne",
    "ListOfTwo",
    "LongText",
    "ProductIdError",
    "ProductId",
    "MigrationSummary",
    "OrganisationId",
    "Timestamp",
    "migration_summary",
    "product_id",
    "remove_empty_items",
    "strEnum",
    "timestamp",
    "unique_conlist",
    "VlanRanges",
    "customer_contact_list",
]
