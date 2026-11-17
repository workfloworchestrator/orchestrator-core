# Copyright 2019-2026 SURF, GÉANT.
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

"""Names of the highlight columns a retriever selects and the result formatter reads.

Kept apart from the retrievers so the formatter can read their rows without importing them.
"""

HIGHLIGHT_TEXT_LABEL = "highlight_text"
HIGHLIGHT_PATH_LABEL = "highlight_path"
HIGHLIGHT_SOURCE_LABEL = "highlight_source"
HIGHLIGHT_MATCHES_LABEL = "highlight_matches"
