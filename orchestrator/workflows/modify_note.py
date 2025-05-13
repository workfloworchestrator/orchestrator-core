# Copyright 2019-2020 SURF, GÉANT.
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
from orchestrator.db import db
from orchestrator.forms import SubmitFormPage
from orchestrator.services import subscriptions
from orchestrator.targets import Target
from orchestrator.utils.json import to_serializable
from orchestrator.workflow import StepList, done, init, step, workflow
from orchestrator.workflows.steps import store_process_subscription
from orchestrator.workflows.utils import wrap_modify_initial_input_form
from pydantic_forms.types import FormGenerator, State, UUIDstr
from pydantic_forms.validators import LongText


def initial_input_form(subscription_id: UUIDstr) -> FormGenerator:
    subscription = subscriptions.get_subscription(subscription_id)
    subscription_backup = {subscription_id: to_serializable(subscription)}
    old_note = subscription.note

    class ModifyNoteForm(SubmitFormPage):
        note: LongText = old_note

    user_input = yield ModifyNoteForm

    return {
        "old_note": old_note,
        "note": user_input.note,
        "__old_subscriptions__": subscription_backup,
    }


@step("Store note")
def store_subscription_note(subscription_id: UUIDstr, note: str) -> State:
    subscription = subscriptions.get_subscription(subscription_id)

    subscription.note = note
    db.session.add(subscription)

    return {
        "subscription": to_serializable(subscription),
    }


@workflow("Modify Note", initial_input_form=wrap_modify_initial_input_form(initial_input_form), target=Target.MODIFY)
def modify_note() -> StepList:
    return init >> store_process_subscription(Target.MODIFY) >> store_subscription_note >> done
