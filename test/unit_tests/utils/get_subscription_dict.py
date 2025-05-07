from unittest import mock
from unittest.mock import Mock

from orchestrator.utils.get_subscription_dict import get_subscription_dict


@mock.patch("orchestrator.utils.get_subscription_dict._generate_etag")
async def test_get_subscription_dict_db(generate_etag, generic_subscription_1):
    generate_etag.side_effect = Mock(return_value="etag-mock")
    await get_subscription_dict(generic_subscription_1)
    assert generate_etag.called
