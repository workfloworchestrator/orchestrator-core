# Introduction

The workflow engine is the core of the orchestrator, it is responsible for the following functions:

* Safely and reliable manipulate customer Subscriptions from one state to the next and maintain auditability.

* Create an API through which Subscriptions can be manipulated programmatically.

* Execute step functions in order and allow the retry of previously failed process-steps in an idempotent way.

* Atomically execute workflow functions.

For more details on what constitutes a workflow, refer to [this section of the example orchestrator.](https://github.com/workfloworchestrator/example-orchestrator?tab=readme-ov-file#workflows-1)

For the purposes of this workshop, we have provided you with already functional workflows that manage the business 
process when updating the lifecycle of product instantiation.

## Node Creation workflow example
The Node Create workflow will be used as an example to describe how a workflow is executed and works. The source code is
avalable in `.orchestrator.workflows.node.create_node.py`

### Create Workflow
{{ external_markdown('https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/README.md', 
'### Create workflow') }}