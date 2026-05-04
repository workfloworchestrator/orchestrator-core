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


from orchestrator.core import OrchestratorCore
from orchestrator.core.cli.main import app as core_cli
from orchestrator.core.domain import SUBSCRIPTION_MODEL_REGISTRY
from orchestrator.core.services.subscriptions import WF_USABLE_MAP
from orchestrator.core.settings import AppSettings
from orchestrator.core.workflows import LazyWorkflowInstance
from test.acceptance_tests.fixtures.test_orchestrator.products.test_product import TestProduct

app = OrchestratorCore(base_settings=AppSettings())

SUBSCRIPTION_MODEL_REGISTRY.update({"TestProduct": TestProduct})

LazyWorkflowInstance("workflows.create_test_product", "create_test_product")
# LazyWorkflowInstance("workflows.terminate_test_product", "terminate_test_product")
# LazyWorkflowInstance("workflows.validate_test_product", "validate_test_product")

WF_USABLE_MAP.update(
    {
        # "validate_test_product": ["initial", "active", "provisioning"],
        "modify_note": ["initial", "active", "provisioning", "migrating", "terminated"],
    }
)

if __name__ == "__main__":
    core_cli()
