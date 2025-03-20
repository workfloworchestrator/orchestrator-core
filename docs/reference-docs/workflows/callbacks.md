# Callbacks

In most workflow steps, when an operation is initiated, it completes and
returns a result within a few seconds. However, if you have (for example)
a longer-lived operation that is triggered through a HTTP request, then
holding the HTTP connection open for the duration is fragile, and could
result in missing the response without the ability to recover.

To handle this scenario, Workflow Orchestrator supports callbacks.

## Using callbacks

When you wish to use a callback, Orchestrator supplies a callback URL that
should be passed to the remote service. When the operation is triggered,
the step immediately completes.

The workflow then pauses until the remote service performs the callback. At
that point, the callback URL is disabled (so further triggers will not
result in a repeat), a validation step is performed, and the result is
provided to the UI.

If the validation step fails, then the step fails and execution of the
workflow is stopped. If the validation step succeeds, then execution
of the workflow is paused, and the operator is prompted for confirmation
before it continues.

## Writing a callback

The only immediate difference between a regular step and one that uses
a callback is the addition of the `callback_route` parameter. This will
be populated by orchestrator.

Here is an example that makes a HTTP request to a service that executes
an Ansible playbook:

```python
from orchestrator import step


@step("Execute an ansible playbook")
def call_ansible_playbook(
    subscription: L2vpnProvisioning,
    callback_route: str,
    *,
    dry_run: bool,
) -> None:
    inventory = f"{port_A.node.node_name}\n{port_B.node.node_name}"
    port_A = subscription.virtual_circuit.saps[0].port
    port_B = subscription.virtual_circuit.saps[1].port

    extra_vars = {
        "vlan": subscription.virtual_circuit.saps[0].vlan,
        "SiteA": f"{port_A.node.node_name}",
        "interfaceA": port_A.port_name,
        "SiteB": f"{port_B.node.node_name}",
        "interfaceB": port_B.port_name,
    }

    callback_url = f"http://orchestrator{callback_route}"

    parameters = {
        "playbook_name": "playbook.yml",
        "inventory": inventory,
        "extra_vars": extra_vars,
        "callback": callback_url,
    }

    url = f"http://ansible-proxy/api/playbook/"
    request = requests.post(url, json=parameters, timeout=10)
    request.raise_for_status()
```

However, this step is not included directly in the step list. To
supplement it, we will need an additional function which also
provides the validation step.

```python
from orchestrator.workflow import Step, callback_step


def callback_interaction(provisioning_step: Step) -> StepList:
    return (
        begin
        >> callback_step(
            name=provisioning_step.name,
            action_step=provisioning_step,
            validate_step=_evaluate_callback_results,
        )
        >> _show_callback_results
    )
```

We also have to provide the evaluation function, and the confirmation step.

The remote service, when performing the callback, should provide a JSON
payload containing the fields that will be evaluated and output in the
UI. In the above example, the service responds with this payload:

```jsonc
{
    "job_id": "example", // UUID
    "output": "example", // From ansible_playbook_run.stdout.readlines()
    "return_code": 0,    // From int(ansible_playbook_run.rc)
    "status": "example"  // From ansible_playbook_run.status
}
```

This allows us, in this example, to use the return code from Ansible to make
the pass/fail decision on the step:

```python
from orchestrator import step
from orchestrator.utils.errors import ProcessFailureError


@step("Evaluate callback result")
def _evaluate_callback_results(callback_result: dict) -> State:
    if callback_result["return_code"] != 0:
        raise ProcessFailureError(message="Callback failure", details=callback_result)

    return {"callback_result": callback_result}
```

Then we also need the step that presents the results to the operator and
requests confirmation before proceeding:

```python
from orchestrator.config.assignee import Assignee
from orchestrator.forms import FormPage
from orchestrator.workflow import Step, inputstep
from pydantic_forms.validators import LongText


@inputstep("Confirm provisioning proxy results", assignee=Assignee("SYSTEM"))
def _show_callback_results(state: State) -> FormGenerator:
    if "callback_result" not in state:
        return state

    class ConfirmRunPage(FormPage):
        class Config:
            title: str = (
                f"Execution for {state['subscription']['product']['name']} completed."
            )

        run_status: str = state["callback_result"]["status"]
        run_results: LongText = json.dumps(state["callback_result"], indent=4)

    yield ConfirmRunPage
    state.pop("run_results")
    return state
```

Finally, we wire this all up in our StepList. Instead of including the step
directly, provide the step as a parameter to the interaction function:

```python
from orchestrator.types import SubscriptionLifecycle
from orchestrator.workflows.utils import create_workflow


@create_workflow("Example workflow", initial_input_form=initial_input_form_generator)
def create_l2vpn() -> StepList:
    return (
        begin
        >> construct_model
        >> store_process_subscription(Target.CREATE)
        >> callback_interaction(call_ansible_playbook)
        >> set_status(SubscriptionLifecycle.ACTIVE)
    )
```

## Callback progress during execution

For long-running jobs, such as executing Terraform or Ansible playbooks, the Orchestrator allows callback jobs to send real-time progress updates which can be used to provide operators with feedback on the progress of the running task.

Progress updates should be delivered to `{callback_route}/progress`, where `"/progress"` is a fixed endpoint appended to the callback URL.

The remote service should send a JSON or plain string payload with each progress callback, this replaces the previous progress update and refreshes the UI. Once the final callback is triggered and the job completes, progress updates are removed, leaving only the callback result. Therefore, all troubleshooting or diagnostic information must be included in the final callback payload, as progress updates are not retained for debugging.
