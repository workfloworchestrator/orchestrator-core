# Optional modules

For the development of optional modules of the Workflow Orchestrator, like `orchestrator-optical`, a submodule in the
`orchestrator.*` namespace can be claimed. As the name already suggests, this package will install the module in
`orchestrator.optical`, and any submodules below it.

To be able to provide this kind of inter-operability, we rely on the fact that **none** of these modules place an
`__init__.py` in the root module `orchestrator`, since that would prevent it from becoming an
[implicit namespace package](https://peps.python.org/pep-0420/).

## Contributing new modules

For the introduction of newly developed optional modules that enricht the Workflow Orchestrator, we would like to ask you to use the template repository provided [here](https://github.com/workfloworchestrator/orchestrator-plugin).

[//]: # "The link to the template repo above will need to be updated as this does not exist yet."
