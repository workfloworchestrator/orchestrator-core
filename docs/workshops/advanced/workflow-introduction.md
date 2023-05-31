# Introduction

The workflow engine is the core of the orchestrator, it is responsible for the following functions:

* Safely and reliable manipulate customer Subscriptions from one state to the next and maintain auditability.

* Create an API through which Subscriptions can be manipulated programmatically.

* Execute step functions in order and allow the retry of previously failed process-steps in an idempotent way.

* Atomically execute workflow functions.

For more details on what constitutes a workflow, refer to [this section of the beginner workshop.](/orchestrator-core/workshops/beginner/workflow-introduction/)
