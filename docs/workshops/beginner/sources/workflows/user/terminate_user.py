from orchestrator.forms import FormPage
from orchestrator.forms.validators import DisplaySubscription
from orchestrator.targets import Target
from orchestrator.types import InputForm, State, SubscriptionLifecycle, UUIDstr
from orchestrator.workflow import done, init, step, workflow
from orchestrator.workflows.steps import resync, set_status, store_process_subscription, unsync
from orchestrator.workflows.utils import wrap_modify_initial_input_form

from products import User


def initial_input_form_generator(subscription_id: UUIDstr, organisation: UUIDstr) -> InputForm:
    temp_subscription_id = subscription_id

    class TerminateForm(FormPage):
        subscription_id: DisplaySubscription = temp_subscription_id  # type: ignore

        # _check_not_in_use_by_nsi_lp: classmethod = root_validator(allow_reuse=True)(validate_not_in_use_by_nsi_lp)

    return TerminateForm


def _deprovision_in_user_management_system(user_id: int) -> int:
    pass


@step("Deprovision user")
def deprovision_user(subscription: User) -> State:
    _deprovision_in_user_management_system(subscription.user.user_id)
    return {"user_deprovision_status": f"deprovisioned user with id {subscription.user.user_id}"}


@workflow(
    "Terminate user",
    initial_input_form=wrap_modify_initial_input_form(initial_input_form_generator),
    target=Target.TERMINATE,
)
def terminate_user():
    step_list = (
        init
        >> store_process_subscription(Target.TERMINATE)
        >> unsync
        >> deprovision_user
        >> set_status(SubscriptionLifecycle.TERMINATED)
        >> resync
        >> done
    )
    return step_list
