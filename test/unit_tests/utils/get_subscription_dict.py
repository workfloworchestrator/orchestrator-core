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
from unittest.mock import Mock

from orchestrator.core.utils.get_subscription_dict import get_subscription_dict


@mock.patch("orchestrator.core.utils.get_subscription_dict._generate_etag")
async def test_get_subscription_dict_db(generate_etag, generic_subscription_1):
    generate_etag.side_effect = Mock(return_value="etag-mock")
    await get_subscription_dict(generic_subscription_1)
    assert generate_etag.called
