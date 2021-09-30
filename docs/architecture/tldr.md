# Architecture; TLDR

The architecture of how the orchestrator-core is setup can be split in two section. The orchestration philosophy of how
workflows are setup and run, and how the application van be used to run your own workflows.

## Application architecture
If you follow the examples in the examples directory and Getting started you should be up and running in a short while.

The Application extends a FastAPI application and therefore can make use of all the awesome features of FastAPI, pydantic
and asyncio python.
