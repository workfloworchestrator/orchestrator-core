# Parallelization in SURF

At SURF, parallelization is implemented through a couple of workarounds rather than a dedicated framework. There are two
distinct patterns: spawning multiple **workflows** in parallel, and running a **step** over many items in a single
workflow. Both are described below.

## Parallel workflows

When a single action needs to be applied to many subscriptions, SURF spawns one child workflow per subscription from a
parent task. The parent task creates the child processes and then hands them off to the orchestrator to be picked up and
run.

A task that spawns parallel workflows is structured as follows. The `restart_created_workflows` step is provided by
orchestrator-core and resumes the processes created in the previous step.

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core.workflows.tasks.resume_workflows import restart_created_workflows


    @task(run_predicate=no_uncompleted_instance)
    def task_sync_crm_customers_to_ripe() -> StepList:
        return (
            begin
            >> create_reconcile_jobs
            >> restart_created_workflows
        )
    ```

The `create_reconcile_jobs` step selects the subscriptions to act on and creates one process per subscription using
`create_process` from orchestrator-core. It returns the created `process_id`s under the `created_state_process_ids` key,
which `restart_created_workflows` reads to resume each process.

=== "`orchestrator-core` ≥ 5.0"

    ```python
    from orchestrator.core.services.processes import create_process


    @step("Create reconcile jobs")
    def create_reconcile_jobs(roles_created: list[dict]) -> State:
        subscriptions = (
            SurfSubscriptionTable.query.join(SurfSubscriptionTable.product)
            .join(SurfSubscriptionTable.customer)
            .filter(...)
            .all()
        )

        process_ids = [
            create_process(
                "reconcile_ip_lir_prefix",
                user_inputs=[{"subscription_id": sub.subscription_id}],
            ).process_id
            for sub in subscriptions
        ]

        return {
            "created_state_process_ids": process_ids,
            "created_reconcile_workflows": [
                f"{app_settings.WORKFLOWS_GUI_URI}/workflows/{process}" for process in process_ids
            ],
        }
    ```

The created child workflows run independently. There is no callback step that waits for the
child workflows to complete; the parent task finishes once the child processes have been started.

## Parallel steps

The second pattern is a "foreach"-style step that processes many items within a single workflow. This is used, for
example, to update all in-use-by subscriptions of a modified subscription. The work is still performed sequentially
inside the step, but it is expressed as a single step that iterates over the related subscriptions.

=== "`orchestrator-core` ≥ 5.0"

    ```python
    @modify_workflow(initial_input_form=initial_input_form_with_checks)
    def modify_sn8_service_port_move() -> StepList:
        return (
            begin
            >> update_service_port_subscription
            >> ...
            >> update_ims_for_all_in_use_by_objects
            >> update_ipam_for_all_in_use_by_objects
            >> update_nso_for_all_in_use_by_subscriptions
        )
    ```

Each of these steps iterates over the list of in-use-by subscriptions and collects the results.

=== "`orchestrator-core` ≥ 5.0"

    ```python
    @step("Update IMS for all related subscriptions")
    def update_ims_for_all_in_use_by_objects(in_use_by_subscriptions: list[SubscriptionInfo]) -> State:
        def get_updated_ims_circuits() -> Iterator[list[ServiceComplete]]:
            for index, item in enumerate(in_use_by_subscriptions):
                yield from _update_subscription_in_ims(index, item["subscription_id"])

        updated_ims_circuits = list(flatten(get_updated_ims_circuits()))
        return {"updated_ims_circuits": updated_ims_circuits}

    @step("Update IPAM for related subscriptions")
    def update_ipam_for_all_in_use_by_objects(in_use_by_subscriptions: list[SubscriptionInfo]) -> State:
        updated_ipam_objects = _update_ipam_for_all_in_use_by_objects(in_use_by_subscriptions)

        return {"updated_ipam_objects": updated_ipam_objects}


    def _update_ipam_for_all_in_use_by_objects(in_use_by_subscriptions: list[SubscriptionInfo]) -> list[list[State]]:
        def update_ipam_object(index: int, item: SubscriptionInfo) -> Generator:
            subscription_id = item["subscription_id"]
            ...  # update IPAM data for in-use-by subscription

        updated_ipam_objects = [update_ipam_object(index, item) for index, item in enumerate(in_use_by_subscriptions)]
        return list(flatten(updated_ipam_objects))
    ```

This pattern keeps everything within a single process, which makes the state easy to inspect, but the work runs
sequentially within the step. When true parallel execution is needed, this can be rewritten to the parallel workflow
workaround described above, spawning one child workflow per in-use-by subscription.
