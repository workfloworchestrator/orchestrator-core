from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeAlias, TypeVar

if TYPE_CHECKING:
    # Only import for static analysis to avoid circular import
    from orchestrator.workflow import Step, Workflow


class AuthUserModel(Protocol):
    @property
    def user_name(self) -> str:
        return ""

    # TODO should I also enforce a "name"? I think things might break otherwise
    # e.g. settings.py::set_status does
    # user_name = oidc_user.name if oidc_user else SYSTEM_USER
    # Or perhaps that should use user_name instead.


# This can't be a Pydantic model while we have circular imports in workflow.py.
@dataclass
class AuthContext:
    # TODO user or user_name?
    user: AuthUserModel | None = None
    workflow: "Workflow | None" = None
    step: "Step | None" = None
    # TODO decide which of these to include
    # request_method: str | None # or a more specific type
    # request_path: str | None
    # request_headers: dict | None
    # request_payload: str | bytes | None


# Can instead use "type Authorizer = ..." in later Python versions.
T = TypeVar("T", bound=AuthContext)
Authorizer: TypeAlias = Callable[[T | None], Awaitable[bool]]
