import strawberry


@strawberry.interface
class BaseError:
    message: str


@strawberry.type
class Error(BaseError):
    message: str


@strawberry.type
class DebugError(BaseError):
    traceback: str
