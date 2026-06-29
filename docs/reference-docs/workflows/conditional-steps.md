# Conditional Steps

`conditional` lets you skip individual workflow steps at runtime based on the
current workflow state. Unlike [run predicates](run-predicates.md), which prevent a
workflow from *starting*, `conditional` controls whether individual steps execute
*during* an already-running workflow.

When a step is skipped:

- The state dictionary is passed through unchanged
- The step is recorded in the process log with a `Skipped` status
- The workflow continues normally — a skipped step is not a failure

## How it works

`conditional(predicate)` takes a callable `(State) -> bool` and returns a
wrapper callable. That wrapper accepts either a single `Step` or a `StepList`
(built with `begin >> ...`) and returns a new `StepList` where every step is
individually guarded by the predicate.

**The predicate is evaluated once per step, not once per group.** When wrapping
multiple steps, the predicate is called again for each step in the group. This
means that if an earlier wrapped step modifies the state in a way that changes
the predicate result, later steps in the same group may behave differently.

## Usage patterns

### Wrapping a single step

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core.workflow import StepList, begin, conditional


    if_has_nodes = conditional(lambda state: len(state["nodes_to_deploy"]) > 0)


    @modify_workflow("Add Nodes", initial_input_form=initial_input_form_generator)
    def add_nodes() -> StepList:
        return (
            begin
            >> if_has_nodes(deploy_nodes)
            >> finalize
        )
    ```

=== "`orchestrator-core` < 5.0"

    ```python
    from orchestrator.workflow import StepList, begin, conditional


    if_has_nodes = conditional(lambda state: len(state["nodes_to_deploy"]) > 0)


    @modify_workflow("Add Nodes", initial_input_form=initial_input_form_generator)
    def add_nodes() -> StepList:
        return (
            begin
            >> if_has_nodes(deploy_nodes)
            >> finalize
        )
    ```

### Wrapping multiple steps

Pass a `StepList` (built with `begin >> ...`) to skip an entire group of steps
under a single condition:

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core.workflow import StepList, begin, conditional


    skip_config = conditional(lambda state: state.get("skip_config") is True)


    @terminate_workflow("Terminate Product", initial_input_form=initial_input_form_generator)
    def terminate_product() -> StepList:
        return (
            begin
            >> skip_config(
                begin
                >> ansible_dryrun
                >> ansible_live
            )
            >> cleanup
        )
    ```

=== "`orchestrator-core` < 5.0"

    ```python
    from orchestrator.workflow import StepList, begin, conditional


    skip_config = conditional(lambda state: state.get("skip_config") is True)


    @terminate_workflow("Terminate Product", initial_input_form=initial_input_form_generator)
    def terminate_product() -> StepList:
        return (
            begin
            >> skip_config(
                begin
                >> ansible_dryrun
                >> ansible_live
            )
            >> cleanup
        )
    ```

### Predicate depending on a prior step's output

A step can write a value to the state, and a subsequent `conditional` can read
it. This pattern is useful when the condition depends on information that must be
fetched at runtime:

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core.workflow import State, StepList, begin, conditional, step


    @step("Check deployment status")
    def check_deployment_status(subscription: MySubscription) -> State:
        return {"is_deployed": check_if_deployed(subscription)}


    _if_deployed = conditional(lambda state: state["is_deployed"])


    @modify_workflow("Modify Product", initial_input_form=initial_input_form_generator)
    def modify_product() -> StepList:
        return (
            begin
            >> check_deployment_status
            >> assemble_payload
            >> _if_deployed(remove_legacy_config)
            >> deploy_changes
        )
    ```

=== "`orchestrator-core` < 5.0"

    ```python
    from orchestrator.workflow import State, StepList, begin, conditional, step


    @step("Check deployment status")
    def check_deployment_status(subscription: MySubscription) -> State:
        return {"is_deployed": check_if_deployed(subscription)}


    _if_deployed = conditional(lambda state: state["is_deployed"])


    @modify_workflow("Modify Product", initial_input_form=initial_input_form_generator)
    def modify_product() -> StepList:
        return (
            begin
            >> check_deployment_status
            >> assemble_payload
            >> _if_deployed(remove_legacy_config)
            >> deploy_changes
        )
    ```

### Reusable conditional sub-pipelines

A `conditional` wrapper and a partial `StepList` can be composed into a reusable
variable and shared across workflows:

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core.workflow import StepList, begin, conditional


    _if_deployed = conditional(lambda state: state["is_deployed"])

    generate_and_store_dry_run: StepList = (
        begin
        >> check_deployment_status
        >> assemble_payload
        >> _if_deployed(remove_legacy_config)
        >> run_dry_run
        >> store_dry_run_results
    )
    ```

=== "`orchestrator-core` < 5.0"

    ```python
    from orchestrator.workflow import StepList, begin, conditional


    _if_deployed = conditional(lambda state: state["is_deployed"])

    generate_and_store_dry_run: StepList = (
        begin
        >> check_deployment_status
        >> assemble_payload
        >> _if_deployed(remove_legacy_config)
        >> run_dry_run
        >> store_dry_run_results
    )
    ```

## API Reference

::: orchestrator.core.workflow.conditional
    options:
        heading_level: 3
