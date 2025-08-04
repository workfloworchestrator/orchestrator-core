> [read more detailed explanation on workflows here](../../architecture/application/workflow.md)

The workflow engine is the core of the software, it has been created to execute a number of functions.

- Safely and reliable manipulate customer `Subscriptions` from one state to the next and maintain auditability.
- Create an API through which programmatically `Subscriptions` can be manipulated.
- Execute step functions in order and allow the retry of previously failed process-steps in an idempotent way.
- Atomically execute workflow functions.

### Best Practices
The orchestrator will always attempt to be as robust as possible when executing workflow steps.
However it is always up to the developer to implement the best practices as well as he/she can.

#### Safeguards in the orchestrator;
- **Atomic Step Execution**: Each step is treated as an atomic unit.
  If a step fails, no partial changes are committed to the database.
  Because of this, calling .commit() on the ORM within a step function is not allowed.
- **`insync` Subscription Requirement**: By default, workflows can only run on subscriptions that are marked as `insync`, unless explicitly configured otherwise.
  This prevents multiple workflows from manipulating the same subscription concurrently.
  One of the first actions a workflow should perform is to mark the subscription as `out of sync` to avoid conflicts.
- **Step Retry Behavior**: Failed steps can be retried indefinitely. Each retry starts from the state of the **last successfully completed** step.


#### Coding gotchas
- The orchestrator is best suited to be used as a data manipulator, not as a data transporter.
  - Use the State log as a log of work, not a log of data.
  - If the data you enter in the state is corrupt or wrong, you might need to attempt a very difficult database query to update the state to solve your conflict.
- Always retrieve external data at the moment it's needed during a step. This increases the robustness of the step.
- Each step function should perform a single, clearly defined unit of work.
  Theoretically you can execute the whole workflow in a single step, However this does not help with traceability and reliability.


### Workshop continued
The following pages try to introduce the workflow concept and how it relates to the product model. All code examples
can be found in the example orchestrator `.workflows.node` directory. Please read at least the following pages to grasp
the functionality of how workflows work and how the user/frontend will interact with the Orchestrator API:

* [Workflow Basics](workflow-basics.md)
* [Create Workflow](node-create.md)
