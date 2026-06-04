# Error tracking

The ``orchestrator-core`` supports [Sentry](https://docs.sentry.io/product/) for
error tracking and performance monitoring. Sentry is an application monitoring
platform that helps developers identify, debug, and resolve issues in their applications by
providing real-time error tracking, performance monitoring, and distributed tracing capabilities.

In order to initialize Sentry (assuming you have already set up a
[Sentry project](https://docs.sentry.io/product/projects/)), perform the following steps:


**1. Update your own `Settings` class**

Add the following attributes to the `Settings` object in your own orchestrator's `settings.py`:

```python
TRACING_ENABLED: bool = False
SENTRY_DSN: str = ""
TRACE_SAMPLE_RATE: float = 0.1
```

```python
# settings.py
from pydantic_settings import BaseSettings

class MySettings(BaseSettings):
    TRACING_ENABLED: bool = False
    SENTRY_DSN: str = ""
    TRACE_SAMPLE_RATE: float = 0.1

my_settings = MySettings()
```

**2. Set environment variables**
```python
TRACING_ENABLED=True
SENTRY_DSN = "your_sentry_dsn" # should be obtained from Sentry
TRACE_SAMPLE_RATE = 0.1 # should be a float between 0 and 1
```
Setting ``TRACING_ENABLED`` to ``True`` will enable tracing for the application, allowing you to monitor
performance and errors more effectively.
!!! note
    - **SENTRY_DSN**: The Data Source Name (DSN) is a unique URL provided by Sentry. It connects your
    application to your Sentry project so errors and performance data are sent to the correct place.
    - **TRACE_SAMPLE_RATE**: A float between 0 and 1 that controls what percentage of transactions
    are sent to Sentry for performance monitoring (e.g., 0.5 means 50% of traces are sampled). See
    Sentry documentation for more details on [sampling](https://docs.sentry.io/concepts/key-terms/sample-rates/).

**3. Update `main.py` file**

Add the following code to the `main.py` file of the `orchestrator-core` application:

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core import OrchestratorCore
    from orchestrator.core.cli.main import app as core_cli
    from orchestrator.core.settings import AppSettings
    from my_orchestrator.settings import my_settings

    app = OrchestratorCore(base_settings=AppSettings())

    if app.base_settings.TRACING_ENABLED and app.base_settings.ENVIRONMENT != "local":
        from orchestrator.core.app import sentry_integrations
        from sentry_sdk.integrations.httpx import HttpxIntegration

        sentry_integrations.append(HttpxIntegration())

        app.add_sentry(
            my_settings.SENTRY_DSN,
            my_settings.TRACE_SAMPLE_RATE,
            app.base_settings.SERVICE_NAME,
            app.base_settings.ENVIRONMENT,
            # before_send=before_send,  # Optional, see section `before_send`
        )

    if __name__ == "__main__":
        core_cli()
    ```

=== "`orchestrator-core` < 5.0"

    ```python
    from orchestrator import OrchestratorCore
    from orchestrator.cli.main import app as core_cli
    from orchestrator.settings import AppSettings
    from my_orchestrator.settings import my_settings

    app = OrchestratorCore(base_settings=AppSettings())

    if app.base_settings.TRACING_ENABLED and app.base_settings.ENVIRONMENT != "local":
        from orchestrator.app import sentry_integrations
        from sentry_sdk.integrations.httpx import HttpxIntegration

        sentry_integrations.append(HttpxIntegration())

        app.add_sentry(
            my_settings.SENTRY_DSN,
            my_settings.TRACE_SAMPLE_RATE,
            app.base_settings.SERVICE_NAME,
            app.base_settings.ENVIRONMENT,
            # before_send=before_send,  # Optional, see section `before_send`
        )

    if __name__ == "__main__":
        core_cli()
    ```

!!! note
    - It's recommended to use separate Sentry projects for different environments (production,
    staging, etc.) to *avoid cluttering production error tracking with development errors*. Many teams
     skip Sentry integration in local development environments.
    - Make sure to adjust the `TRACE_SAMPLE_RATE` according to your needs and test the integration
    in a development environment before deploying it to production.

**4. Test the Sentry integration**

You can test the Sentry integration by triggering an error in your application. For example, you can
 create a route that raises an exception when the endpoint is triggered:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/debug-sentry")
def debug_sentry():
    division_by_zero = 1 / 0
```

!!! warning
    Make sure your environment variable ``ENVIRONMENT`` is **NOT** set to ``local`` when testing the Sentry integration.

## `before_send`

You can define a `before_send` function to perform client-side
event [filtering](https://docs.sentry.io/platforms/python/configuration/filtering/)
and [fingerprinting](https://docs.sentry.io/platforms/python/usage/sdk-fingerprinting/).

Filtering can help to ensure you are only submitting errors for actionable application or infrastructure problems.

Small incomplete example implementation of `before_send` for the API:

```py
from sentry_sdk.types import Event, Hint
from nwastdlib.graphql.extensions.error_handler_extension import EXTENSION_ERROR_TYPE, ErrorType
from graphql.error import GraphQLError

CLIENT_GRAPHQL_ERROR_TYPES = frozenset(
    {
        ErrorType.NOT_AUTHENTICATED,
        ErrorType.NOT_AUTHORIZED,
        ErrorType.NOT_FOUND,
        ErrorType.BAD_REQUEST,
    }
)

def _is_client_graphql_error(exc: GraphQLError) -> bool:
    """True when a GraphQLError was caused by the caller."""
    extensions = exc.extensions or {}
    if extensions.get(EXTENSION_ERROR_TYPE) in CLIENT_GRAPHQL_ERROR_TYPES:
        return True
    return False

def before_send_api(event: Event, hint: Hint) -> Event | None:
    """Sentry ``before_send`` hook to drop or fingerprint an API event."""
    exc_info = hint.get("exc_info")
    exception = exc_info[1] if exc_info else None

    match exception:
        case GraphQLError() if _is_client_graphql_error(exception):
            return None

    # After allowing an event, you can change it's fingerprint or any other aspect to enhance your issue tracking

    return event

# Usage:
# `app.add_sentry(before_send=before_send_api)`
```

Small example for the Celery worker:

```py
import ims_client
from orchestrator.core.utils.errors import InconsistentDataError
from sentry_sdk.types import Event, Hint


def before_send_worker(event: Event, hint: Hint) -> Event | None:
    """Sentry ``before_send`` hook to drop or fingerprint a Worker event."""
    exc_info = hint.get("exc_info")
    exception = exc_info[1] if exc_info else None

    match exception:
        case ims_client.exceptions.NotFoundException():
            return None
        case InconsistentDataError():
            return None

    # After allowing an event, you can change it's fingerprint or any other aspect to enhance your issue tracking

    return event

# Usage:
#   class OrchestratorWorker(Celery):
#       def on_init(self) -> None:
#           if surf_settings.TRACING_ENABLED:
#               sentry_sdk.init(before_send=before_send_worker, ...)
```

**See also**

- [Running the app](../../getting-started/base.md)
- [General info on app settings](../app/settings-overview.md)
