# Copyright 2019-2020 SURF.
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


import re
from datetime import datetime

import pytz

TIMESTAMP_REGEX = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def isoformat(dt: datetime) -> str:
    """ISO format datetime object with max precision limited to seconds.

    Args:
        dt: datatime object to be formatted

    Returns:
        ISO 8601 formatted string

    """
    # IMPORTANT should the format be ever changed, be sure to update TIMESTAMP_REGEX as well!
    return dt.isoformat(timespec="seconds")


def timestamp() -> str:
    """Return iso formatted UTC timestamp as a string.

    Note: precision is in seconds.

    >>> assert TIMESTAMP_REGEX.match(timestamp())

    Returns:
        iso formatted UTC timestamp.

    """
    return isoformat(datetime.utcnow())


def nowtz() -> datetime:
    """Fetch Datetime now object in UTC.

    Returns:
        Datetime object

    """
    return datetime.now(tz=pytz.utc)
