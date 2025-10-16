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

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ExportData(BaseModel):
    """Export metadata for download."""

    action: str = "export"
    query_id: str
    download_url: str
    message: str


class SearchResultsData(BaseModel):
    """Search results metadata for frontend display."""

    action: str = "view_results"
    query_id: str
    results_url: str
    total_count: int
    message: str


class SearchState(BaseModel):
    run_id: UUID | None = None
    query_id: UUID | None = None
    parameters: dict[str, Any] | None = None
    results_data: SearchResultsData | None = None
    export_data: ExportData | None = None
