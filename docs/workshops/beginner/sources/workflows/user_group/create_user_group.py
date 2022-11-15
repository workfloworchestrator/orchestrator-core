from uuid import uuid4

from orchestrator.forms import FormPage
from orchestrator.targets import Target
from orchestrator.types import FormGenerator, State, SubscriptionLifecycle, UUIDstr
from orchestrator.workflow import done, init, step, workflow
from orchestrator.workflows.steps import resync, set_status, store_process_subscription
from orchestrator.workflows.utils import wrap_create_initial_input_form

from products.product_types.user_group import UserGroupInactive, UserGroupProvisioning


def initial_input_form_generator(product_name: str) -> FormGenerator:
    class CreateUserGroupForm(FormPage):
        class Config:
            title = product_name

        group_name: str

    user_input = yield CreateUserGroupForm

    return user_input.dict()


def _provision_in_group_management_system(user_group: str) -> int:

    return abs(hash(user_group))


@step("Create subscription")
def create_subscription(product: UUIDstr) -> State:
    subscription = UserGroupInactive.from_product_id(product, uuid4())

    return {"subscription": subscription, "subscription_id": subscription.subscription_id}


@step("Initialize subscription")
def initialize_subscription(subscription: UserGroupInactive, group_name: str) -> State:
    subscription.user_group.group_name = group_name
    subscription.description = f"User Group {group_name}"
    subscription = UserGroupProvisioning.from_other_lifecycle(subscription, SubscriptionLifecycle.PROVISIONING)

    return {"subscription": subscription}


@step("Provision user group")
def provision_user_group(subscription: UserGroupProvisioning, group_name: str) -> State:
    group_id = _provision_in_group_management_system(group_name)
    subscription.user_group.group_id = group_id

    return {"subscription": subscription}


@workflow(
    "Create user group",
    initial_input_form=wrap_create_initial_input_form(initial_input_form_generator),
    target=Target.CREATE,
)
def create_user_group():

    return (
        init
        >> create_subscription
        >> store_process_subscription(Target.CREATE)
        >> initialize_subscription
        >> provision_user_group
        >> set_status(SubscriptionLifecycle.ACTIVE)
        >> resync
        >> done
    )
