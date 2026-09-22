# Loop Steps

`loop` is `step_group`'s repeating counterpart. It runs a group of steps over and over, checking an exit predicate before each iteration, until that predicate is satisfied or an iteration limit is reached. It has no opinion about why you're looping: polling for a status change, driving an approve/reject cycle, retrying a flaky external call, or driving the turns of a ReAct-style agent loop are all valid uses. `loop` only handles running, suspending, resuming, and (optionally) recovering the repeating steps, and keeps a structured history of what happened in each iteration.

Iterations run back-to-back within a single worker invocation. The step only suspends when a sub-step inside the current iteration suspends (for example an inner `@inputstep`). It never suspends just to move from one iteration to the next.

## How it works

`loop(name, steps, *, until, limit=100, on_error=None)` takes:

- `name`: the step name shown in the process log, and the prefix used for the per-iteration step-group name.
- `steps`: either a static `StepList` used for every iteration, or a callable `(state: State, iteration: int) -> StepList` that builds one iteration's steps from the current state and iteration index. `iteration` is a zero-based counter, incremented each time the previous iteration completes successfully.
- `until`: an exit predicate `(state: State) -> bool`, checked at the top of every iteration, including the first. Once it returns `True`, `loop` returns `Complete`.
- `limit`: the maximum number of iterations. Reaching it without `until` becoming `True` raises `LoopLimitReached`, which surfaces as `Failed`.
- `on_error`: an optional generic recovery hook, described below.

When `steps` is a callable, `loop` calls it again on every resume to reconstruct the iteration in progress, instead of persisting the step list it built. This means the callable must be pure with respect to the state it is given: calling it twice with the same `(state, iteration)` pair must produce a step list with the same shape (the same steps, in the same order). Reading `state["__sub_step"]` is fine, it identifies which sub-step is resuming. The returned step list must not otherwise depend on anything outside `state`.

### State written by `loop`

`loop` owns and writes two keys in process state:

| Key | Purpose |
|-----|---------|
| `loop_steps` | Append-only list mirroring the shape of a process's own step log: `name`, `status`, `state`, `started`, `completed`, plus a `was_suspended` field. One entry per step, in execution order. `status` is a normal step status, or the synthetic `"pending"` for a step that's queued but hasn't run yet. Treat this as read-only; `loop` is the only writer. |
| `loop_steps_branches` | Sidecar map, keyed by the `loop_steps` index at which an `on_error` recovery diverged from the trunk, holding the abandoned tail of entries the recovery cut away. Useful for answering "what would have run if this hadn't been recovered from" without cluttering `loop_steps` itself. |

## Usage patterns

### Static body, looping until a condition holds

```python
from orchestrator.core.workflow import StepList, begin, loop, step


@step("Poll deployment status")
def poll_deployment_status(subscription: MySubscription) -> State:
    return {"deployed": check_if_deployed(subscription)}


poll_until_deployed = loop(
    "Wait for deployment",
    begin >> poll_deployment_status,
    until=lambda state: state.get("deployed") is True,
    limit=30,
)


@modify_workflow("Deploy and confirm", initial_input_form=initial_input_form_generator)
def deploy_and_confirm() -> StepList:
    return (
        begin
        >> trigger_deployment
        >> poll_until_deployed
        >> set_status_active
    )
```

### Re-asking until the input matches

A static body can also re-present the same form on every iteration, for example asking an operator to type a confirmation code until they get it right:

```python
from orchestrator.core.config.assignee import Assignee
from orchestrator.core.workflow import StepList, begin, inputstep, loop, step


@inputstep("Confirm code", assignee=Assignee.NOC)
def confirm_code() -> type[FormPage]:
    class Form(FormPage):
        code: str

    return Form


confirmation_loop = loop(
    "Confirm code",
    begin >> confirm_code,
    until=lambda state: state.get("code") == "1234",
    limit=5,
)


@modify_workflow("Apply change", initial_input_form=initial_input_form_generator)
def apply_change() -> StepList:
    return begin >> prepare_change >> confirmation_loop >> apply_approved_change
```

### Recovering from a failed step with `on_error`

`on_error` receives the same error dict the workflow engine persists for a `Failed` step (`class`, `error`, `traceback`) and the state as it was at the start of the iteration that failed. It can return a replacement `StepList` to run as the rest of that same iteration. The iteration counter does not advance, since recovering from a failure continues the iteration rather than starting a new one. Returning `None` propagates the original failure and `loop` returns `Failed`, exactly as if no `on_error` handler had been given. If `on_error` itself raises, that's treated as a bug in the handler: the exception is logged and the original failure propagates the same way, rather than replacing it.

There is no way to reach a further iteration after a failure other than through the steps `on_error` returns. `loop` never re-derives a next iteration on its own after a failure. If your `steps` builder decides what to run based on a state key, the handler's returned steps need to write that same key themselves, so the builder produces a sensible result the next time `loop` calls it.

`on_error` can be called more than once for the same failure, and the state it receives is not always the same. Right after the failure it gets the full state. If the replacement `StepList` itself suspends (for example it contains an `@inputstep`) and `loop` later needs to regenerate that step, it calls `on_error` again with a snapshot that has internal `__`-prefixed keys and the `loop_steps`/`loop_steps_branches` arrays stripped out. Write `on_error` so it only reads ordinary state keys it put there itself, and it will behave the same either way.

`loop` has no opinion about what "recovering" means. That's entirely up to the function you pass in.

```python
from orchestrator.core.workflow import ErrorDict, State, StepList, begin, loop, step


@step("Call flaky external system")
def call_external_system() -> State:
    return {"response": external_system_request()}


def on_error(error: ErrorDict, iteration_start_state: State) -> StepList | None:
    if error["class"] != "ExternalSystemTimeout":
        return None  # not ours to handle, propagate
    return StepList([wait_and_retry])


retrying_loop = loop(
    "Call external system",
    begin >> call_external_system,
    until=lambda state: "response" in state,
    limit=5,
    on_error=on_error,
)
```

## API Reference

::: orchestrator.core.workflow.loop
    options:
        heading_level: 3
