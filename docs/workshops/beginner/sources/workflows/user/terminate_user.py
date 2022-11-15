from orchestrator.forms import FormPage
from orchestrator.forms.validators import Label
from orchestrator.targets import Target
from orchestrator.types import InputForm, SubscriptionLifecycle, UUIDstr
from orchestrator.workflow import done, init, step, workflow
from orchestrator.workflows.steps import resync, set_status, store_process_subscription, unsync
from orchestrator.workflows.utils import wrap_modify_initial_input_form

from products import User


def initial_input_form_generator(subscription_id: UUIDstr, organisation: UUIDstr) -> InputForm:
    subscription = User.from_subscription(subscription_id)

    class TerminateForm(FormPage):
        are_you_sure: Label = f"Are you sure you want to remove {subscription.description}?"  # type:ignore

    return TerminateForm


def _deprovision_in_user_management_system(user_id: int) -> int:
    pass


@step("Deprovision user")
def deprovision_user(subscription: User) -> None:
    _deprovision_in_user_management_system(subscription.user.user_id)


@workflow(
    "Terminate user",
    initial_input_form=wrap_modify_initial_input_form(initial_input_form_generator),
    target=Target.TERMINATE,
)
def terminate_user():

    return (
        init
        >> store_process_subscription(Target.TERMINATE)
        >> unsync
        >> deprovision_user
        >> set_status(SubscriptionLifecycle.TERMINATED)
        >> resync
        >> done
    )
