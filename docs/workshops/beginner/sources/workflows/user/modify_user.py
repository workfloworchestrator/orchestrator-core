import structlog
from orchestrator.forms import FormPage
from orchestrator.targets import Target
from orchestrator.types import FormGenerator, State, UUIDstr
from orchestrator.workflow import done, init, step, workflow
from orchestrator.workflows.steps import resync, store_process_subscription, unsync
from orchestrator.workflows.utils import wrap_modify_initial_input_form

from products.product_types.user import User
from products.product_types.user_group import UserGroup
from workflows.user.create_user import user_group_selector

logger = structlog.get_logger(__name__)


def initial_input_form_generator(subscription_id: UUIDstr) -> FormGenerator:
    subscription = User.from_subscription(subscription_id)

    class ModifyUserForm(FormPage):
        username: str = subscription.user.username
        age: int | None = subscription.user.age
        user_group_id: user_group_selector() = [str(subscription.user.group.owner_subscription_id)]  # type:ignore

    user_input = yield ModifyUserForm

    return user_input.dict()


def _modify_in_user_management_system(username: str, age: int) -> None:
    pass


@step("Modify subscription")
def modify_user_subscription(
    subscription: User,
    username: str,
    age: int,
    user_group_id: str,
) -> State:
    _modify_in_user_management_system(username, age)
    subscription.user.username = username
    subscription.user.age = age
    subscription.user.group = UserGroup.from_subscription(user_group_id[0]).user_group
    subscription.description = (
        f"User {username} from group {subscription.user.group.group_name} ({subscription.affiliation})"
    )

    return {
        "subscription": subscription,
    }


@workflow(
    "Modify user",
    initial_input_form=wrap_modify_initial_input_form(initial_input_form_generator),
    target=Target.MODIFY,
)
def modify_user():
    step_list = (
        init >> store_process_subscription(Target.MODIFY) >> unsync >> modify_user_subscription >> resync >> done
    )

    return step_list
