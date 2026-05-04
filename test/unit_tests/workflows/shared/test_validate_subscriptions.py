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

from unittest import mock

import pytest

from orchestrator.core.db import SubscriptionTable, db
from orchestrator.core.workflow import StepList, begin, step
from orchestrator.core.workflows.utils import validate_workflow
from pydantic_forms.exceptions import FormValidationError
from test.unit_tests.workflows import (
    WorkflowInstanceForTests,
    assert_complete,
    assert_failed,
    extract_error,
    run_workflow,
)


@validate_workflow()
def validation_workflow() -> StepList:
    return StepList([])


def test_happy_flow(generic_subscription_1, validation_workflow_instance):
    product = db.session.get(SubscriptionTable, generic_subscription_1).product
    product.workflows.append(validation_workflow_instance)
    db.session.add(product)
    db.session.commit()
    result, process, step_log = run_workflow("validation_workflow", {"subscription_id": generic_subscription_1})
    assert_complete(result)


def test_no_subscription(validation_workflow_instance):
    with pytest.raises(FormValidationError) as error_info:
        run_workflow("validation_workflow", {"subscription_id": None})
    assert "UUID input should be a string, bytes or UUID object".lower() in str(error_info.value).lower()


def test_failed_validation(generic_subscription_1: str) -> None:
    @step("Fail")
    def fail():
        raise ValueError("Failed")

    @validate_workflow()
    def failing_validation_workflow() -> StepList:
        return begin >> fail

    with mock.patch.object(db.session, "rollback"):
        with WorkflowInstanceForTests(failing_validation_workflow, "failing_validation_workflow") as failing_wf:
            product = SubscriptionTable.query.get(generic_subscription_1).product
            product.workflows.append(failing_wf)
            db.session.add(product)
            db.session.commit()

            result, process, step_log = run_workflow(
                "failing_validation_workflow", {"subscription_id": generic_subscription_1}
            )
            assert_failed(result)
            assert "Failed" in extract_error(result)
