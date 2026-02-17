# Settings overview in Orchestrator

You can use the `api/settings/overview` endpoint to get an overview of the settings that are used in the application.
This endpoint provides a JSON response that contains the settings that are defined in the application. The settings are
grouped by their names and sensitive values are masked for security reasons.
Per default, the application settings are used to configure the application. The settings are defined in the
`orchestrator.settings.py` module and can be used to configure the application.

An example of the settings is shown below:

```python
from orchestrator.settings import BaseSettings


class AppSettings(BaseSettings):
    TESTING: bool = True
    SESSION_SECRET: OrchSecretStr = "".join(secrets.choice(string.ascii_letters) for i in range(16))  # type: ignore
    CORS_ORIGINS: str = "*"
    ...
    EXPOSE_SETTINGS: bool = False
    EXPOSE_OAUTH_SETTINGS: bool = False


app_settings = AppSettings()

if app_settings.EXPOSE_SETTINGS:
    expose_settings("app_settings", app_settings)  # type: ignore

if app_settings.EXPOSE_OAUTH_SETTINGS:
    expose_settings("oauth2lib_settings", oauth2lib_settings)  # type: ignore
```

What you see above is the default settings for the application. The settings are defined in the
`orchestrator.settings.py` module and can be used to configure the application.
The `EXPOSE_SETTINGS` and `EXPOSE_OAUTH_SETTINGS` flags are used to control whether the settings should be exposed via
the `api/settings/overview` endpoint, the result looks like this:

```json
[
  {
    "name": "app_settings",
    "variables": [
      {
        "env_name": "TESTING",
        "env_value": false
      },
      {
        "env_name": "SESSION_SECRET",
        "env_value": "**********"
      },
      {
        "env_name": "CORS_ORIGINS",
        "env_value": "*"
      }
    ]
  }
]
```

The `app_settings` in the example above is a name of the settings class that is registered to be exposed.

## Exposing your settings

In order to expose your settings, you need to register them using the `expose_settings()` function. This function takes
two arguments: the name of the settings class and the instance of the settings class.

```python
from orchestrator.settings import expose_settings, BaseSettings


class MySettings(BaseSettings):
    debug: bool = True


my_settings = MySettings()

expose_settings("my_settings", my_settings)
```

## Lifecycle Validation Mode

The Lifecycle Validation Mode is used to validate in workflow steps that a **subscription model has been instantiated with the correct product type class for its lifecycle status**. E.g. a subscription model with a lifecycle status of `PROVISIONING` should be instantiated with a product type class that has a lifecycle status of `PROVISIONING`.

You can run the application with three different lifecycle validation modes:

```Python
class LifecycleValidationMode(strEnum):
    STRICT = "strict"
    LOOSE = "loose" # default
    IGNORED = "ignored"
```

The Lifecycle Validation Mode can be set using the `LIFECYCLE_VALIDATION_MODE` environment variable. The default setting is `loose`. The different modes are explained below:

- `strict`: The application will enforce strict checks on the lifecycle status of subscription models in workflow steps. If any issues are found, the application will raise an error and stop running.

!!! example "Error in `strict` mode"
    ```bash
    2025-09-26 13:46:56 [error    ] Subscription of type <class 'products.product_types.l3vpn.L3Vpn'> should use <class 'products.product_types.l3vpn.L3VpnProvisioning'> for lifecycle status 'provisioning' [orchestrator.domain.lifecycle] func=re_deploy_nso process_id=6a483f61-c21d-47be-8390-bbd608c59a77 workflow_name=create_l3vpn
    ```

!!! warning
    A workflow failing on this error will not be recoverable, so it is advised to test this in development first.
- `loose`: The application will log warnings for any issues with the lifecycle validation in workflow steps, but it will still run normally.

!!! example "Warning in `loose` mode"
    ```bash
    2025-09-26 13:46:56 [warning    ] Subscription of type <class 'products.product_types.l3vpn.L3Vpn'> should use <class 'products.product_types.l3vpn.L3VpnProvisioning'> for lifecycle status 'provisioning' [orchestrator.domain.lifecycle] func=re_deploy_nso
    ```
- `ignored`: The application will ignore all lifecycle validation issues and run normally.

## Masking Secrets

The following rules apply when exposing settings:

### Rules for Masking Secrets

- `SecretStr` from `from pydantic import SecretStr` are masked.
- `SecretPostgresDsn` from `from orchestrator.settings import SecretPostgresDsn` is masked.
- `SecretRedisDsn` from `from orchestrator.settings import SecretRedisDsn` is masked.

## Overview of AppSettings class

Toggle the source code block below to get a complete overview of the current application settings.
::: orchestrator.settings.AppSettings
    options:
        heading_level: 4
