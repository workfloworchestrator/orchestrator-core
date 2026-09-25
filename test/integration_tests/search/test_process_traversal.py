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

"""Integration test for ProcessTraverser against a real DB-backed process and subscription.

The unit tests in ``test/unit_tests/search/test_process_traversal.py`` exercise the traverser
against mocked ``ProcessTable``/subscription objects. This test instead builds a real process
linked to a real subscription via ``store_process_subscription()``, loads it back through
``ProcessConfig.get_all_query()`` (the same eager-loading query the indexer uses), and asserts
the traverser extracts the expected process and subscription fields from that real ORM graph.
"""

from uuid import UUID

from nwastdlib import const
from orchestrator.core.db import db
from orchestrator.core.search.core.types import EntityType
from orchestrator.core.search.indexing.registry import ENTITY_CONFIG_REGISTRY
from orchestrator.core.services.processes import start_process
from orchestrator.core.targets import Target
from orchestrator.core.workflow import done, init, workflow
from orchestrator.core.workflows.steps import store_process_subscription
from pydantic_forms.core import FormPage
from test.integration_tests.workflows import WorkflowInstanceForTests


def test_traverse_process_with_real_subscription(generic_subscription_1):
    class Form(FormPage):
        subscription_id: UUID

    @workflow(target=Target.SYSTEM, initial_input_form=const(Form))
    def test_traverse_process_subscription():
        return init >> store_process_subscription() >> done

    with WorkflowInstanceForTests(test_traverse_process_subscription, "test_traverse_process_subscription"):
        process_id = start_process("test_traverse_process_subscription", [{"subscription_id": generic_subscription_1}])

        config = ENTITY_CONFIG_REGISTRY[EntityType.PROCESS]
        process = db.session.scalars(config.get_all_query(entity_id=str(process_id))).one()

        extracted_fields = config.traverser.get_fields(
            entity=process, pk_name=config.pk_name, root_name=config.root_name
        )
        field_map = {field.path: field.value for field in extracted_fields}

        # Expire just the eagerly-loaded process_subscriptions collection before the context manager's
        # teardown deletes the workflow: otherwise SQLAlchemy tries to null out the loaded child rows'
        # FK instead of relying on the DB's ON DELETE CASCADE, violating the NOT NULL constraint.
        db.session.expire(process, ["process_subscriptions"])

    assert field_map["process.process_id"] == str(process_id)
    assert field_map["process.workflow_name"] == "test_traverse_process_subscription"
    assert field_map["process.workflow_target"] == Target.SYSTEM.value
    assert field_map["process.last_status"] == "completed"

    assert field_map["process.subscriptions.0.subscription_id"] == str(generic_subscription_1)
    assert field_map["process.subscriptions.0.description"] == "Generic Subscription One"
    assert field_map["process.subscriptions.0.product_name"] == "Product 1"
    assert field_map["process.subscriptions.0.product_tag"] == "GEN1"
