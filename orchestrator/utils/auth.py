from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, TypeAlias, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict

from orchestrator.config.assignee import Assignee
from orchestrator.targets import Target


@runtime_checkable
class AuthUserModel(Protocol):
    """This Protocol models the user data the core provides to authorization callbacks.

    AuthUserModel was designed for compatibility oauth2_lib.OIDCUserModel, but allows
    users to define their own classes satisfying the protocol to accomodate other
    identity backends.
    """

    user_name: str

    # TODO should I also enforce a "name"? I think things might break otherwise
    # e.g. settings.py::set_status does
    # user_name = oidc_user.name if oidc_user else SYSTEM_USER
    # Or perhaps that should instead be updated to use user_name instead.


@runtime_checkable
class AuthStep(Protocol):
    """This Protocol models the Step data the core provides for authorization."""

    name: str
    assignee: Assignee | None


@runtime_checkable
class AuthWorkflow(Protocol):
    """This Protocol models the Workflow data the core provides for authorization."""

    name: str
    description: str
    target: Target
    # Here be dragons: StepList isn't just a list[Step]. It adds extra machinery.
    steps: list[AuthStep]


class AuthContext(BaseModel):
    """A context object passed to Authorizer callbacks; contains all information available for authorization purposes.

    Attaching the actual models (e.g. Workflow) to AuthContext creates a circular import
    issue that Pydantic doesn't support. Using a Protocol instead allows for AuthContext
    to benefit from Pydantic at runtime.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    user: AuthUserModel | None = None
    workflow: AuthWorkflow | None = None
    step: AuthStep | None = None


# Can instead use "type Authorizer = ..." in later Python versions.
T = TypeVar("T", bound=AuthContext)
Authorizer: TypeAlias = Callable[[T | None], Awaitable[bool]]
