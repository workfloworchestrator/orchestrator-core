# Copyright 2019-2026 SURF, GÉANT, ESnet.
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

"""Beta: parallel steps.

Execute several step sequences concurrently as branches of one step. Import them from here::

    from orchestrator.core.beta.parallel import map_parallel, parallel

This API may change incompatibly in a minor release; each such change is listed in the changelog and the upgrade
guide.

The code these functions build stays in stable code: the ``branch_*`` columns and the
``ProcessStepRelationTable`` (``db/models.py``, migration ``18a7c2676fd3``), the API and GraphQL fields
(``schemas/process.py``, ``graphql/schemas/process.py``), ``BranchKind`` and ``BranchSpec`` (``workflow.py``), the
step tree walk and the group-name check (``workflow.py``), the queue settings (``settings.py``) and the fork handling
in ``services/processes.py`` and ``utils/enrich_process.py``.

Wiring imports (the exceptions to "stable code doesn't import beta code"):

- ``services/tasks.py`` registers the Celery tasks that call through to
  :mod:`orchestrator.core.beta.parallel.worker`.
- ``workflow.py``'s ``StepList._rshift_dict`` imports ``_make_parallel_step`` inside the function, so the dict form
  ``init >> {"Name": [branch_a, branch_b]}`` keeps working. That form is beta too: it builds the same step as
  :func:`parallel`, it just has no ``beta`` in its import path. Both are listed in ``docs/designs/package-structure.md``.
"""

from orchestrator.core.beta.parallel.dsl import map_parallel, parallel

__all__ = ["map_parallel", "parallel"]
