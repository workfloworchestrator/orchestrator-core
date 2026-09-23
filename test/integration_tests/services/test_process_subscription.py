# Copyright 2026 GÉANT.
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


from uuid import UUID

import pytest
from sqlalchemy.exc import NoResultFound

from nwastdlib import const
from orchestrator.core.config.assignee import Assignee
from orchestrator.core.db import ProcessSubscriptionTable, db
from orchestrator.core.targets import Target
from orchestrator.core.workflow import done, init, inputstep, step, workflow
from orchestrator.core.workflows.steps import store_process_subscription
from pydantic_forms.core import FormPage
from pydantic_forms.types import State, UUIDstr
from test.integration_tests.workflows import (
    WorkflowInstanceForTests,
    assert_complete,
    assert_suspended,
    extract_state,
    resume_workflow,
    run_workflow,
)

CUSTOMER_ID: str = "f962d204-816a-4d7d-862a-3b4b4a42021a"


def test_process_subscription_relation_is_idempotent(generic_subscription_1):
    class Form(FormPage):
        subscription_id: UUID

    @workflow(target=Target.SYSTEM, initial_input_form=const(Form))
    def test_store_process_subscription():
        return (
            init >> store_process_subscription() >> store_process_subscription() >> store_process_subscription() >> done
        )

    with WorkflowInstanceForTests(test_store_process_subscription, "test_store_process_subscription"):
        result, _, _ = run_workflow("test_store_process_subscription", [{"subscription_id": generic_subscription_1}])

        assert_complete(result)
        state = extract_state(result)
        db.session.query(ProcessSubscriptionTable).filter(
            ProcessSubscriptionTable.process_id == state["process_id"],
            ProcessSubscriptionTable.subscription_id == state["subscription_id"],
        ).one()


def test_process_subscription_none_for_task(generic_subscription_1):
    class Form(FormPage):
        subscription_id: UUID

    @workflow(target=Target.VALIDATE, initial_input_form=const(Form))
    def test_store_process_subscription():
        return init >> done

    with WorkflowInstanceForTests(test_store_process_subscription, "test_store_process_subscription"):
        result, _, _ = run_workflow("test_store_process_subscription", [{"subscription_id": generic_subscription_1}])

        assert_complete(result)
        state = extract_state(result)
        with pytest.raises(NoResultFound):
            db.session.query(ProcessSubscriptionTable).filter(
                ProcessSubscriptionTable.process_id == state["process_id"]
            ).one()


def test_process_subscription_relation_stored_in_workflow(generic_subscription_1):
    class Form(FormPage):
        subscription_id: UUID

    @workflow(target=Target.MODIFY, initial_input_form=const(Form))
    def test_store_process_subscription():
        return init >> done

    with WorkflowInstanceForTests(test_store_process_subscription, "test_store_process_subscription"):
        result, _, _ = run_workflow("test_store_process_subscription", [{"subscription_id": generic_subscription_1}])

        assert_complete(result)
        state = extract_state(result)
        db.session.query(ProcessSubscriptionTable).filter(
            ProcessSubscriptionTable.process_id == state["process_id"],
            ProcessSubscriptionTable.subscription_id == state["subscription_id"],
        ).one()


def test_process_subscription_relation_stored_in_create_workflow(generic_product_1, generic_product_type_1):
    @inputstep("Suspended", assignee=Assignee.SYSTEM)
    def suspend():
        class WaitForm(FormPage):
            pass

        yield WaitForm
        return {}

    @step("Create new subscription")  # type: ignore[untyped-decorator]
    def create_subscription(process_id: UUIDstr) -> State:
        GenericProductOneInactive, _ = generic_product_type_1
        gen_subscription = GenericProductOneInactive.from_product_id(
            generic_product_1.product_id, process_id=process_id, customer_id=CUSTOMER_ID, insync=True
        )
        return {"subscription": gen_subscription, "subscription_id": gen_subscription.subscription_id}

    @workflow(target=Target.CREATE, initial_input_form=const(FormPage))
    def test_store_process_subscription():
        return init >> suspend >> create_subscription >> done

    with WorkflowInstanceForTests(test_store_process_subscription, "test_store_process_subscription"):
        result, process, step_log = run_workflow("test_store_process_subscription", {})
        state = extract_state(result)
        assert_suspended(result)
        with pytest.raises(NoResultFound):
            db.session.query(ProcessSubscriptionTable).where(
                ProcessSubscriptionTable.process_id == state["process_id"]
            ).one()

        result, _ = resume_workflow(process, step_log, {})
        assert_complete(result)

        state = extract_state(result)
        db.session.query(ProcessSubscriptionTable).where(
            ProcessSubscriptionTable.process_id == state["process_id"],
            ProcessSubscriptionTable.subscription_id == state["subscription_id"],
        ).one()
