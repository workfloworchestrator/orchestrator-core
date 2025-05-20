from collections.abc import Callable
from typing import TypeAlias

from oauth2_lib.fastapi import OIDCUserModel

# This file is broken out separately to avoid circular imports.

# Can instead use "type Authorizer = ..." in later Python versions.
Authorizer: TypeAlias = Callable[[OIDCUserModel | None], bool]
