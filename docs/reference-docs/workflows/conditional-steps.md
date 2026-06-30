# Conditional Steps

`conditional` lets you skip individual workflow steps at runtime based on the
current workflow state. Unlike [run predicates](run-predicates.md), which prevent a
workflow from _starting_, `conditional` controls whether individual steps execute
_during_ an already-running workflow.

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
    from pydantic_forms.types import FormGenerator, UUIDstr


    def initial_input_form_generator(subscription_id: UUIDstr) -> FormGenerator:
        class ModifyDnsForm(FormPage):
            description: str
            ttl: int = 3600
            new_cname: str | None = None  # leave empty to keep current CNAME

        user_input = yield ModifyDnsForm
        return user_input.model_dump()

    # ... step definitions ...

    if_cname_changed = conditional(lambda state: state.get("new_cname") is not None)


    @modify_workflow(
        "Modify DNS Record",
        initial_input_form=initial_input_form_generator,
    )
    def modify_dns_record() -> StepList:
        return (
            begin
            >> update_subscription
            >> if_cname_changed(notify_customer)
            >> update_dns_in_ipam
            >> set_status_provisioning
        )
    ```

=== "`orchestrator-core` < 5.0"

    ```python
    from orchestrator.workflow import StepList, begin, conditional
    from pydantic_forms.types import FormGenerator, UUIDstr


    def initial_input_form_generator(subscription_id: UUIDstr) -> FormGenerator:
        class ModifyDnsForm(FormPage):
            description: str
            ttl: int = 3600
            new_cname: str | None = None  # leave empty to keep current CNAME

        user_input = yield ModifyDnsForm
        return user_input.model_dump()

    # ... step definitions ...

    if_cname_changed = conditional(lambda state: state.get("new_cname") is not None)


    @modify_workflow(
        "Modify DNS Record",
        initial_input_form=initial_input_form_generator,
    )
    def modify_dns_record() -> StepList:
        return (
            begin
            >> update_subscription
            >> if_cname_changed(notify_customer)
            >> update_dns_in_ipam
            >> set_status_provisioning
        )
    ```

### Wrapping multiple steps

Pass a `StepList` (built with `begin >> ...`) to guard multiple steps with the
same predicate. The predicate is re-evaluated for **each** step individually,
so if a step **within** the `StepList` modifies the state, later steps in the
group may be skipped or executed differently:

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core.workflow import StepList, begin, conditional


    if_config_enabled = conditional(lambda state: state.get("config_enabled") is True)


    @terminate_workflow("Terminate Product", initial_input_form=initial_input_form_generator)
    def terminate_product() -> StepList:
        return (
            begin
            >> if_config_enabled(
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


    if_config_enabled = conditional(lambda state: state.get("config_enabled") is True)


    @terminate_workflow("Terminate Product", initial_input_form=initial_input_form_generator)
    def terminate_product() -> StepList:
        return (
            begin
            >> if_config_enabled(
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


    if_deployed = conditional(lambda state: state["is_deployed"])


    @modify_workflow("Modify Product", initial_input_form=initial_input_form_generator)
    def modify_product() -> StepList:
        return (
            begin
            >> check_deployment_status
            >> assemble_payload
            >> if_deployed(remove_legacy_config)
            >> deploy_changes
        )
    ```

=== "`orchestrator-core` < 5.0"

    ```python
    from orchestrator.workflow import State, StepList, begin, conditional, step


    @step("Check deployment status")
    def check_deployment_status(subscription: MySubscription) -> State:
        return {"is_deployed": check_if_deployed(subscription)}


    if_deployed = conditional(lambda state: state["is_deployed"])


    @modify_workflow("Modify Product", initial_input_form=initial_input_form_generator)
    def modify_product() -> StepList:
        return (
            begin
            >> check_deployment_status
            >> assemble_payload
            >> if_deployed(remove_legacy_config)
            >> deploy_changes
        )
    ```

### Reusing a conditional across workflows

`conditional` can be used as a decorator on a named predicate function. The
resulting wrapper can then be imported and applied to guard different steps in
different workflow modules, keeping predicate logic in one place and avoiding
duplicated lambda expressions:

=== "`orchestrator-core` ≥ 5.0"

    ```python
    # conditions.py — shared conditional predicates
    from orchestrator.core.workflow import State, conditional


    @conditional
    def if_core_node(state: State) -> bool:
        """Guard steps that only apply to core (non-edge) node types."""
        return state["subscription"]["node"]["node_type"] == "core"
    ```

    ```python
    # workflows/redeploy_baseconfig.py
    from orchestrator.core.workflow import StepList, begin

    from products.node.conditions import if_core_node


    @modify_workflow("Redeploy Baseconfig", initial_input_form=input_form_generator)
    def redeploy_baseconfig() -> StepList:
        return (
            begin
            >> generate_config
            >> deploy_config
            >> if_core_node(deploy_boilerplate)
            >> update_descriptions
        )
    ```

    ```python
    # workflows/modify_node.py
    from orchestrator.core.workflow import StepList, begin

    from products.node.conditions import if_core_node


    @modify_workflow("Modify Node", initial_input_form=input_form_generator)
    def modify_node() -> StepList:
        return (
            begin
            >> validate_node
            >> if_core_node(sync_upstream_peers)
            >> apply_changes
        )
    ```

=== "`orchestrator-core` < 5.0"

    ```python
    # conditions.py — shared conditional predicates
    from orchestrator.workflow import State, conditional


    @conditional
    def if_core_node(state: State) -> bool:
        """Guard steps that only apply to core (non-edge) node types."""
        return state["subscription"]["node"]["node_type"] == "core"
    ```

    ```python
    # workflows/redeploy_baseconfig.py
    from orchestrator.workflow import StepList, begin

    from products.node.conditions import if_core_node


    @modify_workflow("Redeploy Baseconfig", initial_input_form=input_form_generator)
    def redeploy_baseconfig() -> StepList:
        return (
            begin
            >> generate_config
            >> deploy_config
            >> if_core_node(deploy_boilerplate)
            >> update_descriptions
        )
    ```

    ```python
    # workflows/modify_node.py
    from orchestrator.workflow import StepList, begin

    from products.node.conditions import if_core_node


    @modify_workflow("Modify Node", initial_input_form=input_form_generator)
    def modify_node() -> StepList:
        return (
            begin
            >> validate_node
            >> if_core_node(sync_upstream_peers)
            >> apply_changes
        )
    ```

## API Reference

::: orchestrator.core.workflow.conditional
options:
heading_level: 3
