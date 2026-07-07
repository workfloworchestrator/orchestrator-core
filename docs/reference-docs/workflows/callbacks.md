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

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core import step


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
=== "`orchestrator-core` < 5.0"

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

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core.workflow import Step, callback_step


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

=== "`orchestrator-core` < 5.0"

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

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core import step
    from orchestrator.core.utils.errors import ProcessFailureError


    @step("Evaluate callback result")
    def _evaluate_callback_results(callback_result: dict) -> State:
        if callback_result["return_code"] != 0:
            raise ProcessFailureError(message="Callback failure", details=callback_result)

        return {"callback_result": callback_result}
    ```

=== "`orchestrator-core` < 5.0"

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

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core.config.assignee import Assignee
    from orchestrator.core.forms import FormPage
    from orchestrator.core.workflow import Step, inputstep
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

=== "`orchestrator-core` < 5.0"

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

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core.types import SubscriptionLifecycle
    from orchestrator.core.workflows.utils import create_workflow


    @create_workflow("Example workflow", initial_input_form=initial_input_form_generator)
    def create_l2vpn() -> StepList:
        return (
            begin
            >> construct_model
            >> store_process_subscription()
            >> callback_interaction(call_ansible_playbook)
            >> set_status(SubscriptionLifecycle.ACTIVE)
        )
    ```

=== "`orchestrator-core` < 5.0"

    ```python
    from orchestrator.types import SubscriptionLifecycle
    from orchestrator.workflows.utils import create_workflow


    @create_workflow("Example workflow", initial_input_form=initial_input_form_generator)
    def create_l2vpn() -> StepList:
        return (
            begin
            >> construct_model
            >> store_process_subscription()
            >> callback_interaction(call_ansible_playbook)
            >> set_status(SubscriptionLifecycle.ACTIVE)
        )
    ```

## Callback progress during execution

For long-running jobs, such as executing Terraform or Ansible playbooks, the Orchestrator allows callback jobs to send real-time progress updates which can be used to provide operators with feedback on the progress of the running task.

Progress updates should be delivered to `{callback_route}/progress`, where `"/progress"` is a fixed endpoint appended to the callback URL.

The remote service should send a JSON or plain string payload with each progress callback, this replaces the previous progress update and refreshes the UI. Once the final callback is triggered and the job completes, progress updates are removed, leaving only the callback result. Therefore, all troubleshooting or diagnostic information must be included in the final callback payload, as progress updates are not retained for debugging.

## Timeouts

By default a callback step waits **indefinitely** for the remote service to call back. If that
service never responds (for example after a network failure), the process stays in
`AWAITING_CALLBACK` forever and the only recovery is manual database intervention.

To guard against this, pass an optional `timeout` (in **seconds**) to `callback_step`:

```python
from orchestrator.core.workflow import callback_step


callback_step(
    name="Call ext system",
    action_step=call_ansible_playbook,
    validate_step=_evaluate_callback_results,
    timeout=300,  # fail if no callback arrives within 5 minutes
)
```

`timeout=None` (the default) keeps the original behaviour of waiting forever, so existing
callbacks are unaffected.

### What happens when the timeout is exceeded

When the deadline passes, the process is moved to `FAILED` with `failed_reason = "Callback timed
out"`. This unblocks the standard recovery actions, so you no longer have to edit the database:

- **Retry** re-runs the *entire callback step group*: it executes the action step again (re-issuing
  the external request and generating a fresh callback URL) and waits anew. Design the action step
  so it is safe to repeat (idempotent, or otherwise tolerant of being run more than once).
- **Abort** marks the process `ABORTED` and stops it. Note that abort does **not** run the
  workflow's remaining steps (the callback cleanup step is skipped) and does **not** itself change
  the subscription's lifecycle state — any follow-up on the subscription is left to the operator or
  a separate workflow.

The deadline is measured from the moment the await started. Progress updates sent to
`{callback_route}/progress` do **not** extend it.

### Enforcement resolution

Timeouts are enforced by the `task_validate_awaiting_callbacks` scheduled task, which sweeps every
**30 seconds** by default. So `timeout` is a *minimum*: a process is failed on the first sweep at or
after its deadline (up to ~30 seconds late) — don't rely on sub-30-second precision. Load the task
with `orchestrator-core scheduler load-initial-schedule`; to change the interval, delete the schedule
and recreate it as a cron schedule at the desired frequency (a 6-field cron can specify seconds, e.g.
`*/15 * * * * *`).
