# Workflows

Workflows are what actually takes a product definition and populates your domain models.
To read more about the architectural design of workflows check out [the architecture page on workflows.](../../architecture/application/workflow.md)
To see more details about the workflow lifecycle states and functions, read on to the next section.


::: orchestrator.core.workflow.ProcessStatus
    options:
        heading_level: 3


::: orchestrator.core.workflows.utils
    options:
        heading_level: 3
        members:
        - create_workflow
        - modify_workflow
        - terminate_workflow
        - validate_workflow
        - reconcile_workflow
        - workflow

::: orchestrator.core.workflow.workflow
    options:
        heading_level: 3


## Workflow helpers to register them in DB
::: orchestrator.core.migrations.helpers
    options:
        heading_level: 3
    members:
    - create
    - ensure_default_workflows
