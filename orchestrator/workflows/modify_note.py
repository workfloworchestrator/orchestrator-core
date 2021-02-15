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


from orchestrator.db import db
from orchestrator.forms import FormPage
from orchestrator.forms.validators import LongText
from orchestrator.services import subscriptions
from orchestrator.targets import Target
from orchestrator.types import FormGenerator, UUIDstr
from orchestrator.workflow import StepList, done, init, workflow
from orchestrator.workflows.steps import store_process_subscription
from orchestrator.workflows.utils import wrap_modify_initial_input_form


def initial_input_form(subscription_id: UUIDstr) -> FormGenerator:
    subscription = subscriptions.get_subscription(subscription_id)
    old_note = subscription.note

    class ModifyNoteForm(FormPage):
        note: LongText = old_note

    user_input = yield ModifyNoteForm
    subscription.note = user_input.note
    db.session.add(subscription)
    return {"old_note": old_note, "note": user_input.note}


@workflow("Modify Note", initial_input_form=wrap_modify_initial_input_form(initial_input_form), target=Target.MODIFY)
def modify_note() -> StepList:
    return init >> store_process_subscription(Target.MODIFY) >> done
