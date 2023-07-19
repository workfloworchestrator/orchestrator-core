from typing import Union

from orchestrator.graphql.schemas.default_customer import DefaultCustomerType
from orchestrator.graphql.schemas.errors import Error
from orchestrator.settings import app_settings


async def resolve_default_customer() -> Union[DefaultCustomerType, Error]:
    customer = app_settings.DEFAULT_CUSTOMER_ONLY
    if not customer:
        return Error(message="DEFAULT_CUSTOMER_ONLY must be set to a value in the environment.")
    return DefaultCustomerType(id=customer)
