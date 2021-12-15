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

from authlib.integrations.starlette_client import OAuth
from nwastdlib.url import URL
from oauth2_lib.fastapi import OIDCUser, opa_decision

from orchestrator.settings import oauth2_settings

oauth_client_credentials = OAuth()

well_known_endpoint = URL(oauth2_settings.OIDC_CONF_WELL_KNOWN_URL)

oauth_client_credentials.register(
    "connext",
    server_metadata_url=well_known_endpoint / ".well-known" / "openid-configuration",
    client_id=oauth2_settings.OAUTH2_RESOURCE_SERVER_ID,
    client_secret=oauth2_settings.OAUTH2_RESOURCE_SERVER_SECRET,
    request_token_params={"grant_type": "client_credentials"},
)

oidc_user = OIDCUser(
    oauth2_settings.OIDC_CONF_WELL_KNOWN_URL,
    oauth2_settings.OAUTH2_RESOURCE_SERVER_ID,
    oauth2_settings.OAUTH2_RESOURCE_SERVER_SECRET,
    enabled=oauth2_settings.OAUTH2_ACTIVE,
)

opa_security_default = opa_decision(oauth2_settings.OPA_URL, oidc_user, enabled=oauth2_settings.OAUTH2_ACTIVE)
