# Copyright 2019-2026 SURF, GÉANT, ESnet.
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

"""Which ``subscription`` queries load the full domain model, and which are served from the subscription table."""

from unittest.mock import MagicMock

import pytest
from strawberry.types.nodes import SelectedField

from orchestrator.core.graphql.resolvers.subscription import _is_subscription_detailed

SCALAR_FIELDS = [
    "subscriptionId",
    "customerId",
    "description",
    "startDate",
    "endDate",
    "status",
    "insync",
    "note",
    "version",
    "__typename",
]

# Resolver fields of SubscriptionInterface. They read from the subscription table (or their own loaders), so
# selecting them must not trigger loading the full domain model.
RESOLVER_FIELDS = [
    "product",
    "customer",
    "customerDescriptions",
    "fixedInputs",
    "productBlockInstances",
    "processes",
    "inUseBySubscriptions",
    "dependsOnSubscriptions",
    "lastValidatedAt",
    "metadata",
]

# Fields that only exist on a product specific subscription type, so they need the domain model.
DOMAIN_MODEL_FIELDS = ["ipPrefix", "vlanRange"]


def _subscription_query(*field_names: str) -> MagicMock:
    root = SelectedField(
        name="subscription",
        directives={},
        arguments={},
        selections=[SelectedField(name=name, directives={}, arguments={}, selections=[]) for name in field_names],
    )
    return MagicMock(selected_fields=[root])


@pytest.mark.parametrize("field_name", [*SCALAR_FIELDS, *RESOLVER_FIELDS])
def test_query_is_not_detailed(field_name: str) -> None:
    assert _is_subscription_detailed(_subscription_query(field_name)) is False


@pytest.mark.parametrize("field_name", DOMAIN_MODEL_FIELDS)
def test_query_for_domain_model_field_is_detailed(field_name: str) -> None:
    assert _is_subscription_detailed(_subscription_query(field_name)) is True


@pytest.mark.parametrize("domain_model_field", DOMAIN_MODEL_FIELDS)
def test_domain_model_field_among_basic_fields_makes_query_detailed(domain_model_field: str) -> None:
    query = _subscription_query(*SCALAR_FIELDS, *RESOLVER_FIELDS, domain_model_field)

    assert _is_subscription_detailed(query) is True


def test_all_basic_fields_together_are_not_detailed() -> None:
    assert _is_subscription_detailed(_subscription_query(*SCALAR_FIELDS, *RESOLVER_FIELDS)) is False
