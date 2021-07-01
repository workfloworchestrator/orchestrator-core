# Product creation readme

- [Introduction](#introduction)
  - [**Create a Product**](#--create-a-product--)
    - [Define your parameters](#define-your-parameters)
    - [Setup the DB](#setup-the-db)
      - [Create the Alembic migrations](#create-the-alembic-migrations)
    - [Create the Product](#create-the-product)
    - [Create the Fixed Inputs](#create-the-fixed-inputs)
    - [Create the Product Block(s)](#create-the-product-blocks)
    - [Create the Resource Type(s)](#create-the-resource-types)
  - [**Create a Workflow**](#--create-a-workflow---)
  - [**Write Validators**](#--write-validators)
  - [**Create NSO Integration (optional)**](#--create-nso-integration--)


## Introduction

This document was created to step through the process of creating a Product within the orchestrator platform, using the "DNS" service as an example.

Some sections will have `Core` and `Legacy` subsections. This is to denote where a step has variations when using the Orchestrator Core vs. the legacy version we started with.

***Dev workflow notes:***

- You may need to add the following line to the `volumes` section of `/orchestrator-compose/docker-compose.yml` file in order to enable modification of migrations
  - `../migrations:/usr/src/app/migrations`
- Migrations can be tested by re-creating the backend and db containers.
  i.e.

  ```shell
  docker ps -a | grep orchestrator | awk '{ print $1 }' | xargs docker container rm
  docker-compose -f <path_to_project>/orchestrator-compose/docker-compose.yml up -d
  ```

- If a failure occurs, clues can typically be found in the traceback seen in the backend Flask log (easiest to see via the docker stdout).

## Create a Product

### Define your parameters

There are a few variables that will need to be consistent across the configured product. Define those before starting.

- product_name:
- workflow_name:
- resource_types: (optional, new resource_types aren't strictly necessary)

### Setup the DB

The database must be configured to accept input from the backend regarding the product/product blocks/resource types we're about to create. This is done with Alembic migration scripts.

#### Create the Alembic migrations

For a detailed look, see `migrations/versions/0002_physical_connection_products.py` and `migrations/versions/0003_physical_connection_products.py`.

```shell
PYTHONPATH=.
FLASK_APP=server.wsgi:app
MIGRATION_NAME=<next_available_number> + <arbitrary product description> + .py
flask db revision --message "MIGRATION_NAME"
touch /migrations/versions/MIGRATION_NAME
```

In an effort to automate the copy-paste nature of creating these migrations, a "create" function was added to helpers.py. Here's a complete example of a migration:

```python
import sqlalchemy as sa
from alembic import op
from migrations.helpers import create
# revision identifiers, used by Alembic.

revision = '123456789abcde'
down_revision = '123456789abcdd'
branch_labels = None
depends_on = None


def upgrade():
    create(op.get_bind(), {
        "products": {
            "ProductTypeName": {
                "product_id": "9e74ab3f-4c0e-4c36-8715-c6cdad4fb958",
                "name": "Product Type",
                "description": "Represents a subscription to a thing",
                "tag": "ProductTypeName",
                "status": "active",
                "product_blocks": [
                    "ProductBlockName"
                ]
            }
        },
        "product_blocks": {
            "ProductBlockName": {
                "product_block_id": "c5a8bfc5-65fb-458b-88ee-f2ef005c0d21",
                "name": "Product Block Name",
                "description": "Models a thing",
                "tag": "PBN",
                "status": "active",
                "resources": {
                    "resource_type_1": "Description of resource",
                    "resource_type_2": "Description of resource"
                }
            }
        },
        "workflows": {
            "workflow_name": {
                "target": "CREATE",
                "description": "Creates a subscription to a Product Type",
                "tag": "WorkflowName",
                "search_phrase": "Workflow Name%",
            }
        }
    })
```

The migrations don't only create schema, they also seed the DB with baked in data as well. So when a new product / block / etc is being created, that data starts in a migration.

When doing this part note that along with creating products, products blocks, resource types and workflows the following DB linkages are made:

- A defined product block gets wired to a product:

```python
    # Link the products and product_blocks
    for block in product_blocks:
        conn.execute(
            sa.text("INSERT INTO product_product_blocks VALUES (:product_id, :product_block_id)"),
            {"product_id": product["product_id"], "product_block_id": block["product_block_id"]},
            )
```

- If a resource type is defined, that gets wired to a product block:

```python
    # wire up resource type to block
    conn.execute(
        sa.text("INSERT INTO product_block_resource_types VALUES (:product_block_id, :resource_type_id)"),
        {"product_block_id": dns_prod_block["product_block_id"], "resource_type_id": dns_resource_type["resource_type_id"],},
    )
```

- And finally, create a new workflow (or workflows) and wire the workflow to the product:

```python
    # workflow creation, wiring to product
    conn.execute(
        sa.text(
            """
        WITH new_workflow AS (
        INSERT INTO workflows(name, target, description)
            VALUES (:name, :target, :description)
            RETURNING workflow_id)
        INSERT
        INTO products_workflows (product_id, workflow_id)
        SELECT
        p.product_id,
        nw.workflow_id
        FROM products AS p
            CROSS JOIN new_workflow AS nw
                WHERE p.tag = :tag
                AND p.name LIKE :search_phrase

    """
        ),
        params_create,
    )
```

- See `0003_physical_connection_products.py` for a somewhat more complex example of that.

### Create the Product

For a detailed look, see `esnetorch/products/product_types/nes.py`.

Products are the umbrella under which all other components sit. Products are the services that will be offered by ESnet. I.e., Physical Connectivity.
[Product component diagram](https://docs.google.com/drawings/d/15r0gkI9Sl7Znc6QCCYrB5V-jc9awoRVSRtUdEAdHuHA/edit?usp=sharing)

Parameters here will dictate values that we expect to have at each phase of the workflow. (e.g., before we move a workflow to 'Provisioning' from 'Inactive', we expect to have the values of X and Y.)

```shell
touch esnetorch/products/product_types/<product name>.py
```

In both the `nes.py` example:

- The base inherits from `SubscriptionModel` and is the product in its inactive state.
- The provisioning state model inherits from that.
- And the actual active product model (`NodeEnrollment`) inherits from that.
- The appropriate product blocks are included in each model.

#### Register new product_type with the `SUBSCRIPTION_MODEL_REGISTRY` object in `esnetorch/products/__init__.py`

##### Core

In the init file import the product type and make an entry in the registry:

```python
from esnetorch.products.product_types.nes import NodeEnrollment

# Register models to actual definitions for deserialization purposes
SUBSCRIPTION_MODEL_REGISTRY.update(
    {
        "Node Enrollment Service": NodeEnrollment,
        # etc etc etc
    }
)
```

Where "Node Enrollment Service" is the name as defined in the migrations.

##### Legacy

(Notes from the legacy orchestrator)

Similar but in `server/domain/product_types/__init__.py`

```python
from server.domain.product_types.pcs import PhysicalConnection
from server.domain.product_types.cts import CircuitTransition
...
    "Physical Connection 100G": PhysicalConnection,
    "Physical Connection 10G": PhysicalConnection,
    "Physical Connection 1G": PhysicalConnection,
    "Circuit Transition Service": CircuitTransition,
}
```

### Add new product types to `server/api/products.py`

#### Core

In the orchestrator core, we no longer need to manually wire the product types into the api. But the tags will be added to `esnetorch/types.py`:

```python
Tags = Literal[
    "NodeEnrollment",
]
```

#### Legacy

(Notes from the legacy orchestrator)

adding `PhysConn` and `CircuitTransition`:

```python
@products.route("/tags/all", strict_slashes=False)
@json_endpoint
def tags() -> Response[List[str]]:
    return (
        [
            "PhysConn",
            "CircuitTransition",
        ],
        HTTPStatus.OK,
    )


@products.route("/types/all", strict_slashes=False)
@json_endpoint
def types() -> Response[List[str]]:
    return (
        ["PhysConn", "CircuitTransition"],
        HTTPStatus.OK,
    )
```

### Create the Fixed Inputs

Fixed Inputs can be thought of as a constraint on the Product that is internally defined inside the Orchestrator database (as opposed to being pulled in from an outside source). It is a variable that exists at the Product level.

Example: the bandwidth associated with "physical connectivity."

These are best avoided or kept to a minimal usage. They can also be used as a model constraint - like *only* 100G or something like that. A product plus a fixed input form a unique composite key.

These are also defined and created in the migrations. The relevant logic and comments from `migrations/versions/0002_physical_connection_products.py`:

```python
        # add fixed inputs to the product - there is a unique together of product with fixed input name, so this
        # means that a product of "Physical Connection 100G" has a fixed input with name "port_speed" and a
        # value of "100000"

        # Later if another product has the same port_speed constraint of 100000, then we create another fixed input row.
        # This will result in the fixed input table having 2 rows that look nearly identical,
        # with the exception that the product_id and fixed_input_id will be different.  It is important that the
        # name remains the same, since in the server/config/fixed_inputs, we use that name to query the db, as well
        # as do other joins on the fixed input names, eg:  "Give me all the products who have port_speed as a
        # fixed input"
        conn.execute(
            sa.text(
                "INSERT INTO fixed_inputs (fixed_input_id, name, value, created_at, product_id) "
                "VALUES (uuid_generate_v4(), 'port_speed', :speed, now(), :product_id)"
            ),
            {"speed": port_speeds[product["name"]], "product_id": product["product_id"]},
        )
```

**Note (in the comments):** since a product + fixed input is a unique composite key there may be situations where the correct thing to do is create what appears to be duplicitous fixed inputs and link them to different products. It is *not the same* as how Product Blocks can be applied to different products.

Register the fixed inputs in `esnetorch/config/__init__.py`

```python
# Fixed inputs
CITY_TYPE = "city_type"
DOMAIN = "domain"
```

### Create the Product Block(s)

For a detailed look, see `esnetorch/products/product_blocks/nes.py`.

Product Blocks can be thought of as a smaller component building block of the Product. The parameters here are used to control the expected value of a given resource type. A Product Block can be applied to multiple products.

They are defined and named thusly:

```shell
touch esnetorch/products/product_blocks/<product_name>.py
```

These files are very similar to how the Products are defined in that the inactive version inherits from `ProductBlockModel`, the provisioning version (`PhysicalConnectionBlockProvisioning`) inherits from that, and the complete/active version (`PhysicalConnectionBlock`) inherits from that.

### Create the Resource Types

Resource Types can be thought of as variables that might be fetched. They are similar to fixed input but are generally pulled in from an external source rather than being internally defined in the Orchestrator. Unlike a fixed input, they apply to a Product Block rather than a Product.

A new resource type is not always required if existing resource types match the desired functionality.

#### Register any new resource types

##### Core

Register resource types in `esnetorch/config/__init__.py`

```python
ESDB_NODE_ID = "esdb_node_id"
ESDB_NODE_URL = "esdb_node_url"
NSO_SERVICE_ID = "nso_service_id"
ROUTING_DOMAIN = "routing_domain"
```

##### Legacy

Register resource types in in `server/config/resource_types.py`

e.g.

```python
class PhysicalConnection(ProductBlock):
    __product_block__ = "Physical Connection"
    __abbrev__ = "PCS"

    ESDB_INTERFACE_ID = "esdb_interface_id"
    NSO_SERVICE_ID = "nso_service_id"


class CircuitTransition(ProductBlock):
    __product_block__ = "Circuit Transition"
    __abbrev__ = "CTS"

    ESNET5_CIRCUIT_ID = "esnet5_circuit_id"
    ESNET6_CIRCUIT_ID = "esnet6_circuit_id"
    SNOW_TICKET_ASSIGNEE = "snow_ticket_assignee"
    SNOW_TICKET_NUMBER = "snow_ticket_number"
```

As these are resource types, these are values that are externally defined in ESDB and Service Now.

- Register each new resource_type in `server/forms/legacy.py` in `MAP_FIELD_TO_VALIDATOR`

### Register any new resource types in the `InputType` in `server/types.py`

#### Core

This step is not used on orchestrator core.

#### Legacy

(Notes from the legacy orchestrator)

e.g.

```python
...
    ## esnet
    "esnet5_circuit_id",
    "esnet6_circuit_id",
    "snow_ticket_number",
    "snow_ticket_assignee",
]
```

## Create a Workflow

for a detailed look, see `esnetorch/workflows/nes/create_node_enrollment.py`:

```shell
mkdir esnetorch/workflows/<product_name>
touch esnetorch/workflows<product_name>/__init__.py
touch esnetorch/workflows/<product_name>/<workflow_name>.py
```

The name of the workflow must match the name in the Alembic migration. The `__init__.py` file can be left empty.

The workflow module must have an `initial_input_form_generator` function. Steps are defined with the `@step("Step description")` decorator. And the actual workflow flow is defined thusly:

```python
@create_workflow(name="Create Physical Connection Service", initial_input_form=initial_input_form_generator)
def create_physical_connection() -> StepList:
    return (
        begin
        >> construct_physical_connection_model
        >> store_process_subscription(Target.CREATE)
        # >> create_esdb_pcs  # store in ESDB
        # >> create_nso_service_model  # reserve port / set description / port inactive
        # >> validate_port  # set port to active and test / service state provisioning - SN ticket?  Does this trigger the IXIA?  Does this use the PBR loop testing?
        # >> place_port_in_service  # activate subscription
    )
```

Where `store_process_subscription` has been defined as a `@step`.

Notes:

- `@inputstep` vs `@step`
  - Input steps stop and wait for the user to input data
- `@create_workflow decorator`
  - Starts with `begin`
  - Takes an initial_input_form and a name
  - The function name needs to match the alembic migration name


### Register the new workflow in the `LazyWorkflowInstance` in `esnetorch/workflows/__init__.py`

e.g.

```python
LazyWorkflowInstance(".pcs.create_pcs", "create_physical_connection")
LazyWorkflowInstance(".circuit_transition.create_transition", "create_circuit_transition")
LazyWorkflowInstance(".pcs.terminate_physical_connection", "terminate_physical_connection")
...
```

#### Additional consideration RE: workflow registration in the orchestrator core

By default the modify workflows that are nested "under" a create workflow like validate or provisioning workflows can only be run on workflows in the `ACTIVE` state (they will appear in the UI but they will be "greyed out" and cannot be executed). But (for example) Create Node Enrollment creates the subscription in a `PROVISIONING` state. There is an additional data structure in this `__init__.py` file that can modify this behavior:

```python
WF_USABLE_MAP.update(
    {
        "validate_node_enrollment": ["active", "provisioning"],
        "provision_node_enrollment": ["active", "provisioning"],
        "modify_node_enrollment": ["provisioning"],
    }
)
```

It sets the states of the main subscription that modify and validate workflows can be run on. Here it allows validate and provision to be run on active and provisioning subs but restricts modify to only be run on provisioning subs.


## Write Validators

Write validation logic in `esnetorch/forms/validators.py`

Validators can cover a variety of needs. They can come into play in a variety of cases:

- Validates input information to ensure that the workflow has all of the information that it needs to execute.
- Type validation: making sure a required subscription is already in place or looking to see if a credit card number matches a given format.
- Can also be used for resource blocking: ensure that a resource the workflow wants to use (like a port) isn't already in use by another workflow that is in flight or done.

Call validation functions in the workflow.

## Create NSO Integration

`XXX(mmg): as of this revision, ESnet is still in the process of getting NSO set up so there are no good examples of configuring this bit yet. This section will need to be updated accordingly by future me.`

For a detailed look, see `/server/domain/services/nso.py`

Other Orchesatrator functions appear to use the Python package `pynso` (`nso_api_client` is a wrapper for this package) to integrate with NSO. This package uses an outdated API endpoint on the NSO server which we no longer use, and should be avoided. Review the  `requests` code used in the DNS Product for insight on how NSO calls should be formed.

### Review `/server/domain/services/nso.py` for existing functionality that might be appropriate for your integration.

If none are present, add a new section:

```python
# -------------------- end of Sn8AggregatedServicePort ---------------

# -------------------- start of DNS --------------------

def get_dns_service(service_name):
    base_url = "http://"+external_service_settings.NSO_HOST+":"+str(external_service_settings.NSO_PORT)+"/restconf/"
    get_headers = {
        'Accept': "application/vnd.yang.collection+xml",
    }

    if service_name:
        get_pm_url = base_url+f"data/tailf-ncs:services/dns:dns={service_name}"
    else:
        get_pm_url = base_url+f"data/tailf-ncs:services/dns:dns"
    print(get_pm_url + "\n")

    # note: this will be empty if the port-mgmt config is completely empty.
    response = requests.request("GET", get_pm_url, data="", headers=get_headers, auth=(external_service_settings.NSO_USER, external_service_settings.NSO_PASS))
    return response.text

def create_dns_service(service_name, domain_name, server_list):
    base_url = "http://"+external_service_settings.NSO_HOST+":"+str(external_service_settings.NSO_PORT)+"/restconf/"
    post_headers = {
        "Content-Type": "application/yang-data+xml"
    }

    # Assert server_list is at least three items long
    if len(server_list) < 3:
        raise ValueError("Must provide 3 server addresses")

    addrs = server_list.replace(' ','').split(',')

    new_dns_server = f'''
                <dns xmlns="http://es.net/dns"  xmlns:dns="http://es.net/dns"  xmlns:ncs="http://tail-f.com/ns/ncs">
                    <name>{service_name}</name>
                    <device-group xmlns="http://es.net/dns">test-empty-group</device-group>
                    <domain-name>{domain_name}</domain-name>
                    <dns-server xmlns="http://es.net/dns">
                        <name>{addrs[0]}</name>
                        <ipv4-address>{addrs[0]}</ipv4-address>
                    </dns-server>
                    <dns-server xmlns="http://es.net/dns">
                        <name>{addrs[1]}</name>
                        <ipv4-address>{addrs[1]}</ipv4-address>
                    </dns-server>
                    <dns-server xmlns="http://es.net/dns">
                        <name>{addrs[2]}</name>
                        <ipv4-address>{addrs[2]}</ipv4-address>
                    </dns-server>
                </dns>'''

    get_pm_url = base_url+f"data/tailf-ncs:services/dns:dns={service_name}"

    # note: this will be empty if the port-mgmt config is completely empty.
    response = requests.request("PUT", get_pm_url, data=new_dns_server, headers=post_headers, auth=(external_service_settings.NSO_USER, external_service_settings.NSO_PASS))
    print(response.text)
    return response.ok

# -------------------- end of DNS --------------------
```

### Import your new function in a workflow (.e.g `/server/workflows/dns/create_dns.py`) like so:

```python
from server.domain.services.nso import <new_nso_function>
```

Requirements:

- Modify `/server/settings.py` to include appropriate NSO integration settings (e.g., `nso-netlab` for dev purposes)

Notes:

- For hints on the appropriate path for `get` requests from NSO, connect to the NSO CLI and run a `show` command with `display json`. e.g.:

```shell
ssh nso-netlab.es.net
ncs_cli -u admin -J
show configuration services dns | display json

expected output:
{
  "data": {
    "tailf-ncs:services": {
      "dns:dns": [
        {...
```
