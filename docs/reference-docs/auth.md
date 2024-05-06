# Authentication and Authorization
## Overview
The `Orchestrator-Core` application incorporates a robust security framework, utilizing OpenID Connect (OIDC) for authentication and Open Policy Agent (OPA) for authorization. 
This flexible system ensures secure access, allowing you to tailor the authorization components to best fit your application's specific requirements.

## Authentication
In `Orchestrator-Core`, authentication is managed through OIDC to confirm user identities and control access to various endpoints.

### OIDCAuth Configuration
The `OIDCAuth` class manages OIDC authentication processes including token validation and retrieval of user information. Below is a configuration example:

```python
from oauth2_lib.fastapi import OIDCAuth, OIDCUserModel

# Initialize OIDC Authentication
oidc_auth = OIDCAuth(
    openid_url="https://example-opendid.com",
    openid_config_url="https://example-opendid.com/.well-known/openid-configuration",
    resource_server_id="your-client-id",
    resource_server_secret="your-client-secret",
    oidc_user_model_cls=OIDCUserModel
)
```

## Authorization
Authorization is handled by OPA, providing detailed control over user permissions based on defined policies.

### OPAAuthorization Setup
Configure OPA for authorization using the following setup:

```python
from oauth2_lib.fastapi import OPAAuthorization, GraphQLOPAAuthorization

# Establish OPA Authorization
opa_auth = OPAAuthorization(opa_url="https://opa.example.com/v1/data/your_policy")
graphql_opa_auth = GraphQLOPAAuthorization(opa_url="https://opa.example.com/v1/data/your_policy")
```

## Customizing Authentication and Authorization
### AuthManager
`AuthManager` serves as the central unit for managing both `authentication` and `authorization` mechanisms. 
While it defaults to using `OIDCAuth` for authentication, `OPAAuthorization` for http authorization and `GraphQLOPAAuthorization` for graphql authorization , it supports extensive customization.

### Implementing Custom Authentication:
To implement a custom authentication strategy, extend the abstract `Authentication` base class and implement the `authenticate` method.

### Implementing Custom Authorization:
For custom authorization, extend the `Authorization` class and implement the `authorize` method.

### Implementing Custom GraphQL Authorization:
To customize GraphQL authorization, extend the `GraphqlAuthorization` class and implement the `authorize` method.

Below is an example illustrating how to override the default configurations:

```python
from orchestrator import OrchestratorCore, app_settings
from oauth2_lib.fastapi import OIDCAuth, OIDCUserModel, Authorization, RequestPath, GraphqlAuthorization
from oauth2_lib.settings import oauth2lib_settings
from httpx import AsyncClient
from starlette.requests import HTTPConnection
from typing import Optional

class CustomOIDCAuth(OIDCAuth):
    async def userinfo(self, async_request: AsyncClient, token: str) -> OIDCUserModel:
        # Custom implementation to fetch user information
        return OIDCUserModel(
            sub="user-sub",
            email="example-user@company.org",
            # ...
        )

class CustomAuthorization(Authorization):
    async def authorize(self, request: HTTPConnection, user: OIDCUserModel) -> Optional[bool]:
        # Implement custom authorization logic
        return True
    
class CustomGraphqlAuthorization(GraphqlAuthorization):
    async def authorize(self, request: RequestPath, user: OIDCUserModel) -> Optional[bool]:        
        # Implement custom GraphQL authorization logic
        return True
    
oidc_instance = CustomOIDCAuth(
    openid_url=oauth2lib_settings.OIDC_BASE_URL,
    openid_config_url=oauth2lib_settings.OIDC_CONF_URL,
    resource_server_id=oauth2lib_settings.OAUTH2_RESOURCE_SERVER_ID,
    resource_server_secret=oauth2lib_settings.OAUTH2_RESOURCE_SERVER_SECRET,
    oidc_user_model_cls=OIDCUserModel,
)

authorization_instance = CustomAuthorization()
graphql_authorization_instance = CustomGraphqlAuthorization()

app = OrchestratorCore(base_settings=app_settings)
app.register_authentication(oidc_instance)
app.register_authorization(authorization_instance)
app.register_graphql_authorization(graphql_authorization_instance)
```

## Security Considerations
- Ensure secure HTTPS communications for all OIDC and OPA interactions.
- Securely store sensitive information like client secrets.
- Regularly revise OIDC and OPA configurations to align with evolving security standards and changes in external services.

