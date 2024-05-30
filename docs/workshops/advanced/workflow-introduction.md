The workflow engine is the core of the orchestrator, it is responsible for the following functions:

* Safely and reliable manipulate customer Subscriptions from one state to the next and maintain auditability.
* Create an API through which Subscriptions can be manipulated programmatically.
* Execute step functions in order and allow the retry of previously failed process-steps in an idempotent way.
* Atomically execute workflow functions.

### Best Practices
The orchestrator will always attempt to be a robust a possible when executing workflow steps. However it is always
up to the developer to implement the best practices as well as he/she can.

#### Safeguards in the orchestrator;
* Steps will be treated as atomic units: All code must execute otherwise the state will not be commited to the
  database. For this reason it is not possible to call `.commit()` on the ORM within a step function
* Workflows are only allowed to be run on `insync` subscriptions, unless explicitly configured otherwise. This is to
  safeguard against resource contention. One of the first things a workflow should do is set the subscription it it
  manipulating `out of sync`. No other workflow can then manipulate it.
* Failed steps can be retried again and again, they use the state from the **last successful** step as their
  starting point.

#### Coding gotchas
* The orchestrator is best suited to be used as a data manipulator, not as a data transporter. Use the State log as
  a log of work, not a log of data. If the data you enter in the state is corrupt or wrong, you might need to
  attempt a very difficult database query to update the state to solve your conflict
* Always fetch data needed from an external system, **Just in time**. This will increase the robustness of the step
* Always create a step function that executes one piece of work at a time. Theoretically you can execute the whole
  workflow in a single  step. However this does not help with traceability and reliability.


### Workshop continued
The following pages try to introduce the workflow concept and how it relates to the product model. All code examples
can be found in the example orchestrator `.workflows.node` directory. Please read at least the following pages to grasp
the functionality of how workflows work and how the user/frontend will interact with the Orchestrator API:

* [Workflow Basics](workflow-basics.md)
* [Create Workflow](node-create.md)
