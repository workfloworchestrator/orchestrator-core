# Workflow Steps

Workflows are what actually takes a product definition and populates your domain models. To read more about the architectural design of workflows check out [the architecture page on workflows.](../../architecture/application/workflow.md) To see more details about the types of steps that are available for use, read on to the next section.

## Step Types

::: orchestrator.workflow
    options:
        heading_level: 3
        members:
        - step
        - retrystep
        - inputstep
        - stepgroup
        - callbackstep
        - conditional

## Database Implications

Because a workflow is tied to a product type, this means that you will need a new database migration when adding new workflows. Thankfully, the CLI tool will help you with this! Check out the [CLI docs for `db migrate-workflows`](../cli.md#orchestrator.cli.database.migrate_workflows) for more information.

## Building a Step Function Signature

One important detail that is very helpful to understand is how your Step Function's python function signature is used to deserialize objects from the database into something you can use in your workflow python code. The WFO achieves this by introspecting the step function signature for the type hints you've defined and then tries to populate the appropriate objects for you. To understand the details of how this works, look at this method:

::: orchestrator.utils.state.inject_args
    options:
        heading_level: 3
