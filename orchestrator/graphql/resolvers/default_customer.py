from typing import Union

from orchestrator.graphql.schemas.default_customer import DefaultCustomerType
from orchestrator.graphql.schemas.errors import Error
from orchestrator.settings import app_settings


async def resolve_default_customer() -> Union[DefaultCustomerType, Error]:
    try:
        return DefaultCustomerType(
            fullname=app_settings.DEFAULT_CUSTOMER_FULLNAME,
            shortcode=app_settings.DEFAULT_CUSTOMER_SHORTCODE,
            identifier=app_settings.DEFAULT_CUSTOMER_IDENTIFIER,
        )
    except Exception as e:
        return Error(message=f"Error returning default customer: {str(e)}")
