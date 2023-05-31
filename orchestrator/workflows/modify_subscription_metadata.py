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
from orchestrator.settings import app_settings
from orchestrator.targets import Target
from orchestrator.types import FormGenerator, UUIDstr
from orchestrator.utils.json import to_serializable
from orchestrator.workflow import StepList, conditional, done, init, workflow
from orchestrator.workflows.steps import cache_domain_models, store_process_subscription
from orchestrator.workflows.utils import wrap_modify_initial_input_form


def initial_input_form(subscription_id: UUIDstr) -> FormGenerator:
    subscription = subscriptions.get_subscription(subscription_id)
    subscription_backup = {subscription_id: to_serializable(subscription)}
    old_metadata = "{}"

    class ModifySubscriptionMetadataForm(FormPage):
        metadata: LongText = old_metadata

    user_input = yield ModifySubscriptionMetadataForm

    return {
        "old_metadata": old_metadata,
        "metadata": user_input.metadata,
        "subscription": to_serializable(subscription),
        "__old_subscriptions__": subscription_backup,
    }


@workflow("Modify Subscription Metadata", initial_input_form=wrap_modify_initial_input_form(initial_input_form), target=Target.MODIFY)
def modify_subscription_metadata() -> StepList:
    push_subscriptions = conditional(lambda _: app_settings.CACHE_DOMAIN_MODELS)
    return init >> store_process_subscription(Target.MODIFY) >> push_subscriptions(cache_domain_models) >> done
