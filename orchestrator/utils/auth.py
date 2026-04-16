# Copyright 2019-2026 SURF, ESnet.
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

from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection
from typing import Literal, Protocol, TypeAlias, TypeVar, runtime_checkable

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
    action: Literal["start_workflow", "resume_workflow", "retry_workflow"]
    workflow: AuthWorkflow | None = None
    # Should be None for "start_workflow", otherwise set
    step: AuthStep | None = None


# Can instead use "type Authorizer = ..." in later Python versions.
T = TypeVar("T", bound=AuthContext)
Authorizer: TypeAlias = Callable[[T], Awaitable[bool]]
