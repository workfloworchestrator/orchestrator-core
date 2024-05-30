# Philosophy
The Workflow Orchestrator is a framework of tools that help the developer create workflow to modify the lifecycle of
subscribed products. It is un-opinionated in what it can orchestrate, but very opinionated in how. The Orchestrator is
designed to run linear workflows that represent the business process of delivering a product. In comparison to other
workflow engines like [Camunda](https://camunda.com/) or [Airflow](https://airflow.apache.org/index.html) we try to keep
the options of the developer limited. In most cases the Workflow Orchestrator framework is flexible enough to
handle the intelligence needed in the business process.

## Lightweight
The core functionality of the framework is relatively simple:

* There is a simple step engine that executes python functions.
* Every step is designed to be atomic to make execution as safe as possible.
* When using the Workflow Orchestrator with the example-ui, it is possible to create highly dynamic [forms](../../reference-docs/forms.md) in
Python. The developer does not need to implement any code in the frontend to get started straight away.
* Furthermore we are working on an extensive set of [tools](../../reference-docs/cli.md) to help bootstrap the development experience.
