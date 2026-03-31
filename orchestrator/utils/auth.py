from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection
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

    # mypy really hates `user_name: str`, because this is a read-only property on OIDCUserModel.
    # Using a read-only property on the Protocol should still match implementations with a read/write attribute instead.
    @property
    def user_name(self) -> str:
        return ""

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
class AuthStepList(Collection[AuthStep], Protocol):
    """This models a minimal Protocol for a StepList."""

    def map(self, f: Callable) -> AuthStepList:
        pass


@runtime_checkable
class AuthWorkflow(Protocol):
    """This Protocol models the Workflow data the core provides for authorization."""

    name: str
    description: str
    target: Target

    # Here be dragons! First, StepList isn't just a list[Step]. It adds extra machinery and typing,
    # and it confuses static type checkers. So the following will make mypy barf:
    # `steps: list[AuthStep]`, `steps: collections.abc.Collection[AuthStep]`, and even `steps: AuthStepList`.
    @property
    def steps(self) -> AuthStepList:
        pass


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
