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

"""Workflow designer: compose task workflows from existing steps at runtime, without code changes or migrations.

A designed workflow is stored as a definition (initial form fields and an ordered list of step references) next to a
normal `workflows` row. `source.designed_workflows` builds it into a `Workflow` on demand, so every process that
resolves workflows with `get_workflow` (API, workers, scheduler, CLI) finds it.

This package is imported while `orchestrator.core.workflows` loads, so this module must stay import free.
"""
