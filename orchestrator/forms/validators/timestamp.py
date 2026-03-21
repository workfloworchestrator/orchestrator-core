from datetime import datetime
from typing import Annotated, Callable

import structlog
from pydantic.functional_validators import AfterValidator

from pydantic_forms.validators import timestamp

logger = structlog.get_logger(__name__)


DATE_FORMAT = "DD-MMM-YYYY HH:mm z"  # 19-Mar-2026 00:00 UTC
TIME_FORMAT = "HH:mm"  # 00:00


def validator_min_date(min_date: datetime | None) -> Callable[[int], int]:
    def _validate_min_date(timestamp: int) -> int:
        if min_date and timestamp < min_date.timestamp():
            raise ValueError("start_date must not be in the past")
        return timestamp

    return _validate_min_date


def to_timestamp_field(min_date: datetime | None = None) -> type:
    min_value = int(min_date.timestamp()) if min_date else None
    timestamp_field = timestamp(
        locale="nl-nl",
        min=min_value,
        validate=False,  # We want to raise custom error messages
        date_format=DATE_FORMAT,
        time_format=TIME_FORMAT,
    )

    return Annotated[
        timestamp_field,  # type: ignore
        AfterValidator(validator_min_date(min_date)),
    ]
