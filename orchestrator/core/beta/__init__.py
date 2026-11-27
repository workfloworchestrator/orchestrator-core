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

"""Beta features that need real-world use before their API settles.

A beta feature is a package ``orchestrator/core/beta/<feature>/``. Its public API is what that package's
``__init__.py`` exports; everything else is internal and may change in a minor release. Beta code may import stable
code, and stable code doesn't import beta code, except in wiring modules that register a beta feature with the
framework. Such wiring imports are listed in the feature's ``__init__.py`` docstring.

See ``docs/designs/package-structure.md`` for the full policy.
"""
