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

## Masking Secrets

The following rules apply when exposing settings:

### Rules for Masking Secrets

- Keys containing `"password"` or `"secret"` in their names are masked.
- `SecretStr` from `from pydantic import SecretStr` are masked.
- `SecretStr` from `from orchestrator.utils.expose_settings import SecretStr` are masked.
- `PostgresDsn` from `from pydantic import PostgresDsn` are masked.
