# Running the Orchestrator

This document covers how to to run the Orchestrator in the container and give a road map to some of the major "top level" code involved in configuring and executing it.

## Docker

In our version of the Orchestrator, there is a `Dockerfile` at the top level of our application code with additional configuration files in `orchestrator-compose`. By default the `Dockerfile` will build a container that only runs the back end, but there are directives that can be un-commented to build a version that runs the scheduler as well.

For more details about the scheduler, see `TASKS.md`.

### Building the backend container

You will need to obtain a copy of our deploy key and execute the following commands at the base level where the `Dockerfile` is:

```shell
export SSH_PRIVATE_KEY=`cat ../orchestrator_deploy_key | base64`
docker build -t orchestrator_core:latest --build-arg "SSH_PRIVATE_KEY=$SSH_PRIVATE_KEY" --build-arg "CI_COMMIT_SHA=mmglocal1" .
```

Modifying the path to your deploy key as needed. The `CI_COMMIT_SHA` argument can be any arbitrary string.

### Building the frontend

This is more straightforward. Just cd into `orchestrator-client-compose` and execute:

```shell
docker-compose -f docker-compose.yml up
```

## Top level execution code roadmap

There are a few files that work together to execute the code stack and load custom functionality.

### Entry point - `/bin/server`

This shell script is what is executed by the container. It sets a couple of variables like http port but the main things going on are:

1. Invokes and loads `main.py`.
2. Which also runs the command to apply the alembic migrations.
3. Invokes the gunicorn/uvicorn process.

### `main.py`

This is where the main `OrchestratorCore` app gets instantiated. This can be fairly bare bones, but this is also where you could pass additional settings and options to the `OrchestratorCore` object and bootstrap any additional custom code:

```python
from esnetorch import load_esnet
from orchestrator.cli.main import app as core_cli

def init_app() -> OrchestratorCore:
    logger.info("INIT APP")
    app = OrchestratorCore(base_settings=AppSettings())
    load_esnet(app)
    return app

app = init_app()

if __name__ == "__main__":
    core_cli()
```

### `esnetorch/__init__.py`

This file is at the root of "our" application code hierarchy. Application code is loaded here and also importantly, where the custom API functionality gets loaded. Here is the function being invoked by `main.py`:

```python
def load_esnet(app: OrchestratorCore) -> None:
    import esnetorch.products  # noqa: F401  Side-effects
    import esnetorch.schedules  # noqa: F401  Side-effects
    import esnetorch.workflows  # noqa: F401  Side-effects
    from esnetorch.api.api_v1.api import api_router
    app.include_router(api_router)
```

#### esnetorch.products

This `__init__` file is where the specific products get registered:

```python
from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY

from esnetorch.products.product_types.nes import NodeEnrollment

# Register models to actual definitions for deserialization purposes
SUBSCRIPTION_MODEL_REGISTRY.update(
    {
        "Node Enrollment Service": NodeEnrollment,
        # etc etc etc
    }
)
```

Where "Node Enrollment Service" is the name defined in the product migration:

```python
node_enrollment = dict(
    product_id=str(uuid4()),
    name="Node Enrollment Service",
    description="Node Enrollment Service",
    product_type="NodeEnrollment",
    tag="NodeEnrollment",
    status="active",
)
```

And the imported file is the base product domain model.

#### esnetorch.schedules

This `__init__` file is where the scheduler "crontab" files get loaded to be handled by the scheduler. Those schedule files will invoke the related tasks. See `TASKS.md` for more information about that.

```python
from orchestrator.schedules import ALL_SCHEDULERS

# from surf.schedules.cache_warmer import run_cache_warmer

ALL_SCHEDULERS.extend(
    [
        # run_cache_warmer,
    ]
)
```

#### esnetorch.workflows

This is another big `__init__` file - this is where the workflows are registered. If a workflow isn't registered or this file is not imported at startup, the workflow will not be found.

```python
from orchestrator.services.subscriptions import WF_BLOCKED_BY_PARENTS, WF_USABLE_MAP
from orchestrator.workflows import LazyWorkflowInstance

# Node Enrollment
LazyWorkflowInstance("esnetorch.workflows.nes.create_node_enrollment", "create_node_enrollment")
LazyWorkflowInstance("esnetorch.workflows.nes.validate_node_enrollment", "validate_node_enrollment")
LazyWorkflowInstance("esnetorch.workflows.nes.provision_node_enrollment", "provision_node_enrollment")
LazyWorkflowInstance("esnetorch.workflows.nes.modify_node_enrollment", "modify_node_enrollment")

WF_USABLE_MAP.update(
    {
        "validate_node_enrollment": ["active", "provisioning"],
        "provision_node_enrollment": ["active", "provisioning"],
        "modify_node_enrollment": ["provisioning"],
    }
)
```

The `LazyWorkflowInstance` invocations register the workflows into the execution stack. The first arg is the code module and the second arg is the name of the main workflow entry point:

```python
@create_workflow(
    "Create Node Enrollment",
    initial_input_form=initial_input_form_generator,
    status=SubscriptionLifecycle.PROVISIONING
)
def create_node_enrollment() -> StepList:
    return (
        begin
        >> construct_node_enrollment_model
        ...
        ...
    )
```

The `WF_USABLE_MAP` data structure defines the behavior of the product workflows associated with the main create one. The default behavior is the associated workflows (modify, validate, etc) can only be run on workflows with the subscription state set to `ACTIVE`. They will show up in the UI but can't be executed.

In this example the validate and provision workflows can be run on a main workflow in either the active or provisioning state (which is how node enrollment create set it) and the modify workflow is constrained such that it can only be run on a subscription in the provisioning state but not one that is active.

#### api_router

This part of the invocation:

```python
    from esnetorch.api.api_v1.api import api_router
    app.include_router(api_router)
```

Wires the FastAPI endpoints into the server. That file defines the router (or multiple ones) and wires in the router from a specific endpoint module:

```python
from fastapi.param_functions import Depends
from fastapi.routing import APIRouter

from esnetorch.api.api_v1.endpoints import esdb

api_router = APIRouter()

api_router.include_router(esdb.router, prefix="/api")
```

And the endpoints file defines additional routers and wired in the actual logic to be executed:

```python
from fastapi import APIRouter

from esnetorch.utils.external import esdb_api_client

router = APIRouter(prefix="/esdb")

@router.get("/organisations")
def organisations():

    orgs = esdb_api_client._get_list("organization", query_params={"detail": "list", "types": "ESnet Site"})

    return sorted(
        map(lambda org: {"name": f"{org['short_name']}::{org['full_name']}", "uuid": org['uuid'], "abbr": org['short_name']}, orgs),
        key=lambda x: x["name"],
    )
```

So with the "stacked" routers the ultimate URI of that endpoint would be `/api/esdb/organisations`.

