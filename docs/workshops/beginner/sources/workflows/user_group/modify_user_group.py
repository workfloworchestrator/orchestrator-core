from orchestrator.forms import FormPage, ReadOnlyField
from orchestrator.targets import Target
from orchestrator.types import FormGenerator, State, UUIDstr
from orchestrator.workflow import done, init, step, workflow
from orchestrator.workflows.steps import resync, store_process_subscription, unsync
from orchestrator.workflows.utils import wrap_modify_initial_input_form

from products.product_types.user_group import UserGroup


def initial_input_form_generator(subscription_id: UUIDstr) -> FormGenerator:
    subscription = UserGroup.from_subscription(subscription_id)

    class ModifyUserGroupForm(FormPage):
        group_name: str = subscription.user_group.group_name
        group_id: int = ReadOnlyField(subscription.user_group.group_id)

    user_input = yield ModifyUserGroupForm

    return user_input.dict()


def _modify_in_group_management_system(group_id: int, group_name: str) -> None:
    pass


@step("Modify user group")
def modify_user_group_subscription(subscription: UserGroup, group_name: str) -> State:
    _modify_in_group_management_system(subscription.user_group.group_id, group_name)
    subscription.user_group.group_name = group_name
    subscription.description = f"User Group {group_name}"

    return {"subscription": subscription}


@workflow(
    "Modify user group",
    initial_input_form=wrap_modify_initial_input_form(initial_input_form_generator),
    target=Target.MODIFY,
)
def modify_user_group():

    return (
        init >> store_process_subscription(Target.MODIFY) >> unsync >> modify_user_group_subscription >> resync >> done
    )
