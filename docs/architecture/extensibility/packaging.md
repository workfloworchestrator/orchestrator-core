# Packaging

For the distribution of the `orchestrator-core`, from version `5.0.0` onwards we make use of a namespace package.
Namespace packages are a way to allow a single package name to be split across multiple, independent distributions.
More information on this can be found in the [PEP 420](https://peps.python.org/pep-0420/).


## Why

With the addition of new features to the Orchestrator core, we have reached a point where some new functionality may
be useful to only a subset of the users of Workflow Orchestrator. This increases the footprint and complexity of the
installed library, without the benefits of having a more comprehensive featureset.

For this reason, we want to support a modular approach to the namespace of modules that are distributed as part of
`orchestrator.*`. This way, we can do independent versioning, dependency management, implementation work, and we avoid
one large monolithic codebase that becomes hard to maintain.

## How this enables a pluggable Orchestrator

With the namespacing approach to packaging the Workflow Orchestrator, only the necessary features are provided in the
module installed by `orchestrator-core`. This package will then only claim the namespace under the module
`orchestrator.core.*`.

For any optional modules that are developed outside of this core library, they can claim any other submodule like `orchestrator.X.*`.
