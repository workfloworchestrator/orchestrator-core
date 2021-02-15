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


from orchestrator.workflow import StepList, workflow


# This workflow has been made to create the initial import process for a SN7 subscription
# it does not do anything but is needed for the correct showing in the GUI.
@workflow("Dummy workflow to replace removed workflows")
def removed_workflow() -> StepList:
    return StepList()
