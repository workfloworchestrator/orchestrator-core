# Introduction

orchestrator-core is a workflow engine, built in Python on top of FastAPI and Pydantic.
It allows to manage the lifecycle of customer-facing and resource-facing products.

A product is defined as a collection of `ProductBlock`s and `ResourceType`s. Subscribing a customer to a product
creates a `Subscription`, and workflows move that subscription through its lifecycle: `Initial`, `Provisioning`,
`Active`, `Terminated`. A workflow is a list of Python functions, executed in order by the engine, each storing its
result to the database so it can be retried from that point if it fails.

Start with [Getting Started](getting-started/versions.md) to install and run the orchestrator, or
[Architecture](architecture/tldr.md) for how it's put together.
