import pytest


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

    fastapi_app.register_graphql()
    return fastapi_app
