# Copyright 2019-2026 SURF, GÉANT.
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

from unittest import mock

import pytest

from orchestrator.core.graphql.autoregistration import register_domain_models


@pytest.fixture(autouse=True)
def load_fixtures(
    generic_product_type_1,
    generic_product_type_2,
    test_product_type_sub_list_union,
    test_product_type_sub_one,
    test_product_type_sub_two,
    product_type_1_subscriptions_factory,
    sub_one_subscription_1,
    sub_two_subscription_1,
    product_sub_list_union_subscription_1,
):
    print("Loading fixtures")
    pass


@pytest.fixture(scope="session", autouse=True)
def fix_graphql_model_registration():
    # This block caches the "ProductBlockListNestedForTestInactive" model to avoid re-instantiation in each test case.
    # This is necessary because this product block has a self referencing property, which strawberry can't handle correctly,
    # and lead to an error expecting the `ProductBlockListNestedForTestInactive` strawberry type to already exist.
    internal_graphql_models = {}

    def patched_register_domain_models(*args, **kwargs):
        graphql_models = register_domain_models(*args, **kwargs)
        internal_graphql_models.update(graphql_models)
        return internal_graphql_models

    with mock.patch(
        "orchestrator.core.graphql.schema.register_domain_models", side_effect=patched_register_domain_models
    ):
        yield
