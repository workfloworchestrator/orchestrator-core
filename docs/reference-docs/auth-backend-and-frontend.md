# Authentication and authorization

The `Orchestrator-Core` application incorporates a robust security framework, utilizing OpenID Connect (OIDC) for authentication and Open Policy Agent (OPA) for authorization. This flexible system ensures secure access, allowing you to tailor the authorization components to best fit your application's specific requirements.

WFO can be run with or without authentication. With authentication turned on authorization logic can be provided that uses - for example - user privileges to allow further access to resources. Authentication is configured using ENV variables. The frontend and backend have their own set of ENV variables and logic to be implemented to run auth(n/z).

Note: With authentication enabled on the backend the frontend has to have authentication enabled as well. When the frontend has authentication enabled it is possible to run a backend without authentication. Please note the limitations of frontend authentication and authorization mentioned in a note under frontend authentication.

## Definitions

A **frontend application** refers to a web frontend based on the frontend example ui repository: [frontend repo][1]
A **backend application** refers to an application build using the orchestrator core as a base: [backend repo][2]

## Without authentication

Without authentication WFO allows all users access to all resources.

##### Backend

`OAUTH2_ACTIVE=false`

##### Frontend:

`OAUTH2_ACTIVE=false`

## With Authentication

WFO provides authentication based on an OIDC provider. The OIDC provider is presumed to be configured and to provide

-   An authentication endpoint
-   A tenant
-   A client id
-   A client secret

#### Frontend

The WFO frontend uses [NextAuth](3) to handle authentication. Authentication configuration can be found in [page/api/auth/[...nextauth].ts](4)

**ENV variables**
These variables need to be set for authentication to work on the frontend.

```
# Auth variables
OAUTH2_ACTIVE=true
OAUTH2_CLIENT_ID="orchestrator-client" // The oidc client id as configured in the OIDC provider
OAUTH2_CLIENT_SECRET=[SECRET] // The oidc client secret id as configured in the OIDC provider

NEXTAUTH_PROVIDER_ID="keycloak" // String identifying the OIDC provider
NEXTAUTH_PROVIDER_NAME="Keycloak" // The name of the OIDC provider. Keycloak uses this name to display in the login screen
NEXTAUTH_AUTHORIZATION_SCOPE_OVERRIDE="openid profile" // Optional override of the scopes that are asked permission for from the OIDC provider

# Required by the Nextauth middleware
NEXTAUTH_URL=[DOMAIN]/api/auth // The path to the [...nextauth].js file
NEXTAUTH_SECRET=[SECRET] // Used by NextAuth to encrypt the JWT token
```

With authentication turned on and these variables provided the frontend application will redirect unauthorized users to the login screen provided by the OIDC provider to request their credentials and return them to the page they tried to visit.

Note: It's possible to add additional oidc providers including some that are provided by the NextAuth library like Google, Apple and others. See [NextAuthProviders](5) for more information.

##### Authorization

Authorization on the frontend can be used to determine if a page, action or navigation item is shown to a user. For this it uses an `isAllowedHandler` function can be passed into the WfoAuth component that wraps the page in `_app.tsx`

```_app.tsx

...
    <WfoAuth isAllowedHandler={..custom function..}>
    ...
    </WfoAuth>
...
```

The signature of the function should be `(routerPath: string, resource?: string) => boolean;`. The function is called on with the `routerpath` value and
the `resource`. This is the list of events the function is called on is:

```
export enum PolicyResource {
    NAVIGATION_METADATA = '/orchestrator/metadata/', // called when determining if the metadata menuitem should be shown
    NAVIGATION_SETTINGS = '/orchestrator/settings/', // called when determining if the settings menuitem should be shown
    NAVIGATION_SUBSCRIPTIONS = '/orchestrator/subscriptions/', // called when determining if the subscriptions should be shown
    NAVIGATION_TASKS = '/orchestrator/tasks/', // called when determining if the tasks menuitem should be shown
    NAVIGATION_WORKFLOWS = '/orchestrator/processes/', // called when determining if the processes menuitem should be shown
    PROCESS_ABORT = '/orchestrator/processes/abort/', // called when determining if the button to trigger a process abort should be shown
    PROCESS_DELETE = '/orchestrator/processes/delete/', // called when determining if the button to trigger a process delete button should be shown
    PROCESS_DETAILS = '/orchestrator/processes/details/', // called when determining if the process detail page should be displayed
    PROCESS_RELATED_SUBSCRIPTIONS = '/orchestrator/subscriptions/view/from-process', // called when determining if the related subscriptions for a subscription should be shown
    PROCESS_RETRY = '/orchestrator/processes/retry/', // called when determining if the button to trigger a process retry should be shown
    PROCESS_USER_INPUT = '/orchestrator/processes/user-input/', // called when determining if th
    SUBSCRIPTION_CREATE = '/orchestrator/processes/create/process/menu', // called when determining if create if actions that trigger a create workflow should be displayed
    SUBSCRIPTION_MODIFY = '/orchestrator/subscriptions/modify/', // called when determining if create if actions that trigger a modify workflow should be displayed
    SUBSCRIPTION_TERMINATE = '/orchestrator/subscriptions/terminate/', // called when determining if create if actions that trigger a terminate workflow should be displayed
    SUBSCRIPTION_VALIDATE = '/orchestrator/subscriptions/validate/', // called when determining if create if actions that trigger a validate task should be displayed
    TASKS_CREATE = '/orchestrator/processes/create/task', // called when determining if create if actions that trigger a task should be displayed
    TASKS_RETRY_ALL = '/orchestrator/processes/all-tasks/retry', // called when determining if create if actions that trigger retry all tasks task should be displayed
    SETTINGS_FLUSH_CACHE = '/orchestrator/settings/flush-cache', // called when determining if a button to flush cache should be displayed
    SET_IN_SYNC = '/orchestrator/subscriptions/set-in-sync', // called when determining if a button to set a subscription in sync should be displayed
}
```

Note: Components that are hidden for unauthorized users are still part of the frontend application, authorization just makes sure
unauthorized users are not presented with actions they are not allowed to take. The calls these actions
make can still be made through curl calls for example. Additional authorization needs to be implemented on these calls on the backend.

### Backend

**ENV variables**
These variables need to be set for authentication to work on the backend

```
...
# OIDC settings
OAUTH2_ACTIVE: bool = True
OAUTH2_AUTHORIZATION_ACTIVE: bool = True
OAUTH2_RESOURCE_SERVER_ID: str = ""
OAUTH2_RESOURCE_SERVER_SECRET: str = ""
OAUTH2_TOKEN_URL: str = ""
OIDC_BASE_URL: str = ""
OIDC_CONF_URL: str = ""

# OPtional OPA settings
OPA_URL: str = ""
```

With the variables provided, requests to endpoints will return 403 error codes for users that are not logged in and 401 error codes for users that are not authorized to do a call.

#### Customization

`AuthManager` serves as the central unit for managing both `authentication` and `authorization` mechanisms.
While it defaults to using `OIDCAuth` for authentication, `OPAAuthorization` for http authorization and `GraphQLOPAAuthorization` for graphql authorization , it supports customization.

When initiating the `OrchestratorCore` class, it's [`auth_manager`][6] property is set to `AuthManager`. AuthManager is provided by [oauth2_lib][7].

`AuthManager` provides 3 methods that are called for authentication and authorization: `authentication`, `authentication` and `graphql_authorization`.

`authentication`: The default method provided by Oaut2Lib implements returning the OIDC user from the OIDC introspection endpoint.

`authorization`: A method that applies authorization decisions to HTTP requests, the decision is either true (Allowed) or false (Forbidden). Gets this payload to based decisions on. The default method provided by Oaut2Lib uses OPA and sends the payload to the opa_url specified in OPA_URL setting to get a decision.

```
            "input": {
                **(self.opa_kwargs or {}),
                **(user_info or {}),
                "resource": request.url.path,
                "method": request_method,
                "arguments": {"path": request.path_params, "query": {**request.query_params}, "json": json},
            }
```

Note:
The default authentication method allows for the passing in of **is_bypassable_request** method that receives the Request object
and returns a boolean. When this method returns true the request is always allowed regardless of other authorization decisions.

`graphql_authorization`: A method that applies authorization decisions to graphql requests. Specializes OPA authorization for GraphQL operations.
GraphQl results always return a 200 response when authenticated but can return 403 results for partial results as may occur in federated scenarios.

### Customizing

When initializing the app we have the option to register custom authentication and authorization methods and override the default auth(n|z) logic.

```
...
    app.register_authentication(...)
    app.register_authorization(...)
    app.register_graphql_authorization(...)
...
```

**app.register_authentication** takes an subclass of abstract class

```
from abc import ABC, abstractmethod

class Authentication(ABC):
    """Abstract base for authentication mechanisms.

    Requires an async authenticate method implementation.
    """

    @abstractmethod
    async def authenticate(self, request: HTTPConnection, token: str | None = None) -> dict | None:
        """Authenticate the user."""
        pass
```

Authorization decisions can be made based on request properties and the token provided

**app.register_authorization** takes an subclass of abstract class

```
from abc import ABC, abstractmethod

class Authorization(ABC):
    """Defines the authorization logic interface.

    Implementations must provide an async method to authorize based on request and user info.
    """

    @abstractmethod
    async def authorize(self, request: HTTPConnection, user: OIDCUserModel) -> bool | None:
        pass

```

Authorization decisions can be made based on request properties and user attributes

**app.register_graphql_authorization** takes a subclass of abstract class

```
class GraphqlAuthorization(ABC):
    """Defines the graphql authorization logic interface.

    Implementations must provide an async method to authorize based on request and user info.
    """

    @abstractmethod
    async def authorize(self, request: RequestPath, user: OIDCUserModel) -> bool | None:
        pass

```

Graphql Authorization decisions can be made based on request properties and user attributes

### Example

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

[1]: https://github.com/workfloworchestrator/example-orchestrator-ui
[2]: https://github.com/workfloworchestrator/example-orchestrator
[3]: https://next-auth.js.org/
[4]: https://github.com/workfloworchestrator/example-orchestrator-ui/blob/main/pages/api/auth/%5B...nextauth%5D.ts
[5]: https://next-auth.js.org/configuration/providers/oauth
[6]: https://github.com/workfloworchestrator/orchestrator-core/blob/70b0617049dfd25d31cbe3a7e5c8d6e48150f307/orchestrator/app.py#L95
[7]: https://github.com/workfloworchestrator/oauth2-lib
