from collections.abc import Callable
from typing import TypeAlias, TypeVar

from oauth2_lib.fastapi import OIDCUserModel

# This file is broken out separately to avoid circular imports.

# Can instead use "type Authorizer = ..." in later Python versions.
T = TypeVar("T", bound=OIDCUserModel)
Authorizer: TypeAlias = Callable[[T | None], bool]
