# Copyright 2019-2025 SURF, GÉANT.
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

import uuid

from dateutil.parser import isoparse


def is_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def is_iso_date(value: str) -> bool:
    """Check if a string is a valid ISO 8601 date."""
    try:
        isoparse(value)
        return True
    except (ValueError, TypeError):
        return False


def is_bool_string(value: str) -> bool:
    """Check if a string explicitly represents a boolean value with true/false."""

    return value.strip().lower() in {"true", "false"}
