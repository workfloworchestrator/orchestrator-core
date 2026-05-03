# Copyright 2019-2026 ESnet, GÉANT, SURF.
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

from contextlib import contextmanager

from oauth2_lib.settings import oauth2lib_settings


@contextmanager
def mutation_authorization():
    old_oauth2_active = oauth2lib_settings.OAUTH2_ACTIVE
    old_mutations_enabled = oauth2lib_settings.MUTATIONS_ENABLED

    oauth2lib_settings.OAUTH2_ACTIVE = False
    oauth2lib_settings.MUTATIONS_ENABLED = True

    yield

    oauth2lib_settings.OAUTH2_ACTIVE = old_oauth2_active
    oauth2lib_settings.MUTATIONS_ENABLED = old_mutations_enabled
