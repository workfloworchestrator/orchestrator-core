from unittest import mock

import pytest

from orchestrator import app_settings
from orchestrator.graphql.autoregistration import register_domain_models
from test.unit_tests.fixtures.products.product_blocks.product_block_list_nested import (
    ProductBlockListNestedForTestInactiveGraphql,
)


@pytest.fixture(autouse=True)
def fastapi_app_graphql(
    fastapi_app,
    test_client,
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
    from pydantic import BaseModel

    from orchestrator.graphql.schemas.subscription import MetadataDict

    class Metadata(BaseModel):
        some_metadata_prop: list[str]

    MetadataDict.update({"metadata": Metadata})

    actual_env = app_settings.ENVIRONMENT
    app_settings.ENVIRONMENT = "TESTING"
    fastapi_app.register_graphql()
    yield fastapi_app
    app_settings.ENVIRONMENT = actual_env


@pytest.fixture(scope="session", autouse=True)
def fix_graphql_model_registration():
    # This block caches the "ProductBlockListNestedForTestInactive" model to avoid re-instantiation in each test case.
    # This is necessary because this product block has a self referencing property, which strawberry can't handle correctly,
    # and lead to an error expecting the `ProductBlockListNestedForTestInactive` strawberry type to already exist.
    internal_graphql_models = {"ProductBlockListNestedForTestInactive": ProductBlockListNestedForTestInactiveGraphql}

    def patched_register_domain_models(*args, **kwargs):
        graphql_models = register_domain_models(*args, **kwargs)
        internal_graphql_models.update(graphql_models)
        return internal_graphql_models

    with mock.patch("orchestrator.graphql.schema.register_domain_models", side_effect=patched_register_domain_models):
        yield
