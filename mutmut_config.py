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


def pre_mutation(context):
    """Prepare mutmut context.

    This helps skipping needless mutations.
    """
    line = context.current_source_line.strip()
    if context.current_line_index != 0:
        prev_line = context.source_by_line_number[context.current_line_index - 1].strip()
    else:
        prev_line = ""

    if line.startswith("logger.") or prev_line.startswith("logger."):
        context.skip = True
    if line.startswith("logger = structlog"):
        context.skip = True
    if line.startswith("cls.__doc__"):
        context.skip = True

    # This file is copied verbatim and is not tested
    if context.filename.endswith("crypt.py"):
        context.skip = True
