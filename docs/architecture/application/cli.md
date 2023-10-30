# Command line interface commands

Top level options:

--install-completion [bash|zsh|fish|powershell|pwsh]  

Install completion for the specified shell. [default: None]

--show-completion [bash|zsh|fish|powershell|pwsh]  

Show completion for the specified shell, to copy it or customize the
installation. [default: None]

## db

Interact with the application database.

### downgrade

The `main.py db downgrade` command will downgrade the database to the previous
revision or to the optionally specified revision.

Arguments

revision - Rev id to upgrade to [default: -1]

### heads

The `main.py db heads` command shows the Alembic database heads.

### history

The `main.py db history` command lists Alembic revision history in
chronological order.

Options

--verbose - Verbose output  
--current - Indicate current revision

### init

The `main.py db init` command initialises an empty migrations environment.
This command will throw an exception when it detects conflicting files and
directories.

### merge

The `main.py db merge` command merges database revisions.                     

Arguments

revisions - Add the revision you would like to merge to this command 
[default: None]

Options

--message TEXT - The revision message

### migrate-domain-models

The `main.py db migrate-domain-models` command creates a revision based on the
difference between domain models in the source code and those that are defined
in the database.  

Arguments

message - Migration name [default: None] [required]

Options

--test | --no-test - Optional boolean if you don't want to generate a 
migration file [default: no-test]  
--inputs -  stringified dict to prefill inputs [default: {}]  
--updates - stringified dict to map updates instead of 
using inputs [default: {}]  

The `python main.py db migrate-domain-model` CLI command is used to
automatically generate the data migrations that you'll need when you add or
change a Domain Model.  It will inspect your DB and the existing domain models,
analyse the differences and it will generate an Alembic data migration in the
correct folder.

Features:

- detect a new Domain Model attribute / resource type
- detect a renamed Domain Model attribute / resource type
- detect a removed Domain Model attribute / resource type
- detect a new Domain Model
- detect a removed Domain Model
- ability to ask for human input when needed

Below in the documentation these features are discussed in more detail.

!!! warning "BACKUP DATABASE BEFORE USING THE MIGRATION!"

Arguments

- `message`: Message/description of the generated migration.
- `--test`: Optional boolean if you don't want to generate a migration file.
- `--inputs`: stringified dict to prefill inputs.
    The inputs and updates argument is mostly used for testing, prefilling the given inputs, here examples:
    - new product: `inputs = { "new_product_name": { "description": "add description", "product_type": "add_type", "tag": "add_tag" }}`
    - new product fixed input: `inputs = { "new_product_name": { "new_fixed_input_name": "value" }}`
    - new product block: `inputs = { "new_product_block_name": { "description": "add description", "tag": "add_tag" } }`
    - new resource type: `inputs = { "new_resource_type_name": { "description": "add description", "value": "add default value", "new_product_block_name": "add default value for block" }}`
        - `new_product_block_name` prop inserts value specifically for that block.
        - `value` prop is inserted as default for all existing instances it is added to.
- `--updates`: stringified dict to prefill inputs.
    - renaming a fixed input:
        - `updates = { "fixed_inputs": { "product_name": { "old_fixed_input_name": "new_fixed_input_name" } } }`
    - renaming a resource type to a new resource type:
        - `inputs = { "new_resource_type_name": { "description": "add description" }}`
        - `updates = { "resource_types": { "old_resource_type_name": "new_resource_type_name" } }`
    - renaming a resource type to existing resource type: `updates = { "resource_types": { "old_resource_type_name": "new_resource_type_name" } }`

**Example**

You need products in the `SUBSCRIPTION_MODEL_REGISTRY`, for this example I will use these models (taken out of [example-orchestrator](https://github.com/workfloworchestrator/example-orchestrator-beginner)):

- UserGroup Block:
    ```python
    from orchestrator.domain.base import SubscriptionModel, ProductBlockModel
    from orchestrator.types import SubscriptionLifecycle


    class UserGroupBlockInactive(
        ProductBlockModel,
        lifecycle=[SubscriptionLifecycle.INITIAL],
        product_block_name="UserGroupBlock",
    ):
        group_name: str | None = None
        group_id: int | None = None


    class UserGroupBlockProvisioning(
        UserGroupBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        group_name: str
        group_id: int | None = None


    class UserGroupBlock(
        UserGroupBlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]
    ):
        group_name: str
        group_id: int
    ```

- UserGroup Product:
    ```python
    from orchestrator.domain.base import SubscriptionModel
    from orchestrator.types import SubscriptionLifecycle

    from products.product_blocks.user_group import (
        UserGroupBlock,
        UserGroupBlockInactive,
        UserGroupBlockProvisioning,
    )


    class UserGroupInactive(
        SubscriptionModel, is_base=True, lifecycle=[SubscriptionLifecycle.INITIAL]
    ):
        settings: UserGroupBlockInactive


    class UserGroupProvisioning(
        UserGroupInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        settings: UserGroupBlockProvisioning


    class UserGroup(UserGroupProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        settings: UserGroupBlock
    ```

- User Block:
    ```python
    from orchestrator.domain.base import ProductBlockModel
    from orchestrator.types import SubscriptionLifecycle

    from products.product_blocks.user_group import (
        UserGroupBlock,
        UserGroupBlockInactive,
        UserGroupBlockProvisioning,
    )


    class UserBlockInactive(
        ProductBlockModel,
        lifecycle=[SubscriptionLifecycle.INITIAL],
        product_block_name="UserBlock",
    ):
        group: UserGroupBlockInactive
        username: str | None = None
        age: int | None = None
        user_id: int | None = None


    class UserBlockProvisioning(
        UserBlockInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]
    ):
        group: UserGroupBlockProvisioning
        username: str
        age: int | None = None
        user_id: int | None = None


    class UserBlock(UserBlockProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        group: UserGroupBlock
        username: str
        age: int | None = None
        user_id: int
    ```

- User Product:
    ```python
    from orchestrator.domain.base import SubscriptionModel
    from orchestrator.types import SubscriptionLifecycle, strEnum

    from products.product_blocks.user import (
        UserBlock,
        UserBlockInactive,
        UserBlockProvisioning,
    )


    class Affiliation(strEnum):
        internal = "internal"
        external = "external"


    class UserInactive(SubscriptionModel, is_base=True):
        affiliation: Affiliation
        settings: UserBlockInactive


    class UserProvisioning(UserInactive, lifecycle=[SubscriptionLifecycle.PROVISIONING]):
        affiliation: Affiliation
        settings: UserBlockProvisioning


    class User(UserProvisioning, lifecycle=[SubscriptionLifecycle.ACTIVE]):
        affiliation: Affiliation
        settings: UserBlock
    ```

- `SUBSCRIPTION_MODEL_REGISTRY`:
    ```python
    from orchestrator.domain import SUBSCRIPTION_MODEL_REGISTRY

    from products.product_types.user import User
    from products.product_types.user_group import UserGroup

    # Register models to actual definitions for deserialization purposes
    SUBSCRIPTION_MODEL_REGISTRY.update(
        {
            "User group": UserGroup,
            "User internal": User,
            "User external": User,
        }
    )
    ```

Running the command:

- only with a message
    ``` bash
    python main.py db migrate-domain-models "message"
    ```

- Running it as test
    ``` bash
    python main.py db migrate-domain-models "message" --test
    ```

- Running the command with inputs prefilled
    ``` bash
    python main.py db migrate-domain-models "message" --inputs "{ "" }"
    ```

The command will first go through all products and map the differences with the database. debug log example:
```bash
2022-10-27 11:45:10 [debug] ProductTable blocks diff [orchestrator.domain.base] fixed_inputs_in_db=set() fixed_inputs_model=set() missing_fixed_inputs_in_db=set() missing_fixed_inputs_in_model=set() missing_product_blocks_in_db=set() missing_product_blocks_in_model=set() product_block_db=User group product_blocks_in_db={'UserGroupBlock'} product_blocks_in_model={'UserGroupBlock'}
```

You will be prompted with inputs when updates are found.

- rename of resource type input (renaming `age` to `user_age` in User Block). Only works when the resource type is renamed in all Blocks:

    > <u>**Update resource types**</u><br>
	> Do you wish to rename resource type <span style="color:magenta">age</span> to <span style="color:magenta">user_age</span>? [y/N]:

- rename of fixed input (renaming `affiliation` to `affiliationing` in User Product):

    > <u>**Update fixed inputs**</u><br>
    Do you wish to rename fixed input <span style="color:magenta">affiliation</span> to <span style="color:magenta">affiliationing</span> for product **User internal**? [y/N]:

- update of resource type per block (renaming `age` to `user_age` in User Block and not chosing to rename resource type). The input will loop until skipped or when there are no options anymore:
    - first you get to choose which old resource type to update, skip will create/delete all resource types.
        > <u>**Update block resource types**</u><br>
        ```bash
        Which resource type would you want to update in UserBlock Block?
        1) age
        q) skip
        ?
        ```
    - then you get to choose which new resource type to update with, skip will give you the first question again.
        ```bash
        Which resource type should update age?
        1) user_age
        q) skip
        ?
        ```
    - with 1 and 1, the log level difference would look like:
        ```bash
        2023-02-08 14:11:25 [info] update_block_resource_types [orchestrator.cli.migrate_domain_models] update_block_resource_types={'UserBlock': {'age': 'user_age'}}
        ```


It will log the differences on info level:

``` bash
2022-10-27 11:45:10 [info] create_products                   [orchestrator.cli.migrate_domain_models] create_products={'User group': <class 'products.product_types.user_group.UserGroup'>, 'User internal': <class 'products.product_types.user.User'>, 'User external': <class 'products.product_types.user.User'>}
2022-10-27 11:45:10 [info] delete_products                   [orchestrator.cli.migrate_domain_models] delete_products=set()
2022-10-27 11:45:10 [info] create_product_fixed_inputs       [orchestrator.cli.migrate_domain_models] create_product_fixed_inputs={'affiliation': {'User external', 'User internal'}}
2022-10-27 11:45:10 [info] update_product_fixed_inputs       [orchestrator.cli.migrate_domain_models] update_product_fixed_inputs={}
2022-10-27 11:45:10 [info] delete_product_fixed_inputs       [orchestrator.cli.migrate_domain_models] delete_product_fixed_inputs={}
2022-10-27 11:45:10 [info] create_product_to_block_relations [orchestrator.cli.migrate_domain_models] create_product_to_block_relations={'UserGroupBlock': {'User group'}, 'UserBlock': {'User external', 'User internal'}}
2022-10-27 11:45:10 [info] delete_product_to_block_relations [orchestrator.cli.migrate_domain_models] delete_product_to_block_relations={}
2022-10-27 11:45:10 [info] create_resource_types             [orchestrator.cli.migrate_domain_models] create_resource_types={'username', 'age', 'group_name', 'user_id', 'group_id'}
2022-10-27 11:45:10 [info] rename_resource_types             [orchestrator.cli.migrate_domain_models] rename_resource_types={}
2022-10-27 11:45:10 [info] delete_resource_types             [orchestrator.cli.migrate_domain_models] delete_resource_types=set()
2022-10-27 11:45:10 [info] create_resource_type_relations    [orchestrator.cli.migrate_domain_models] create_resource_type_relations={'group_name': {'UserGroupBlock'}, 'group_id': {'UserGroupBlock'}, 'username': {'UserBlock'}, 'age': {'UserBlock'}, 'user_id': {'UserBlock'}}
2022-10-27 11:45:10 [info] delete_resource_type_relations    [orchestrator.cli.migrate_domain_models] delete_resource_type_relations={}
2022-10-27 11:45:10 [info] create_product_blocks             [orchestrator.cli.migrate_domain_models] create_blocks={'UserGroupBlock': <class 'products.product_blocks.user_group.UserGroupBlock'>, 'UserBlock': <class 'products.product_blocks.user.UserBlock'>}
2022-10-27 11:45:10 [info] delete_product_blocks             [orchestrator.cli.migrate_domain_models] delete_blocks=set()
2022-10-27 11:45:10 [info] create_product_block_relations    [orchestrator.cli.migrate_domain_models] create_product_block_relations={'UserGroupBlock': {'UserBlock'}}
2022-10-27 11:45:10 [info] delete_product_block_relations    [orchestrator.cli.migrate_domain_models] delete_product_block_relations={}
```

You will be asked to confirm the actions in order to continue:
> <span style="color:goldenrod">**WARNING:**</span> Deleting products will also delete its subscriptions.<br>
> Confirm the above actions [y/N]:

After confirming, it will start generating the SQL, logging the SQL on debug level and prompt the user for new resources:

- new product example:

    > <u>**Create new products**</u><br>
    Product: UserGroup **User group**<br>
    Supply the production description: User group product<br>
    Supply the product tag: GROUP<br>
    ```sql
    2022-10-27 11:45:10 [debug] generated SQL [orchestrator.cli.domain_gen_helpers.helpers] sql_string=INSERT INTO products (name, description, product_type, tag, status) VALUES ('User group', 'User group product', 'UserGroup', 'GROUP', 'active') RETURNING products.product_id
    ```


- new fixed input (the type isn't checked, so typing an incorrect value will insert in db):

    > <u>**Create fixed inputs**</u><br>
    Supply fixed input value for product **User internal** and fixed input <span style="color:magenta">affiliation</span>: internal<br>
    Supply fixed input value for product **User external** and fixed input <span style="color:magenta">affiliation</span>: external<br>
    ```sql
    2022-10-27 11:45:10 [debug] generated SQL [orchestrator.cli.domain_gen_helpers.helpers] sql_string=INSERT INTO fixed_inputs (name, value, product_id) VALUES ('affiliation', 'internal', (SELECT products.product_id FROM products WHERE products.name IN ('User internal'))), ('affiliation', 'external', (SELECT products.product_id FROM products WHERE products.name IN ('User external')))
    ```

- new product block:

    > <u>**Create product blocks**</u><br>
    Product block: **UserGroupBlock**<br>
    Supply the product block description: User group settings<br>
    Supply the product block tag: UGS<br>
    ```sql
    2022-10-27 11:45:10 [debug] generated SQL [orchestrator.cli.domain_gen_helpers.helpers] sql_string=`#!sql INSERT INTO product_blocks (name, description, tag, status) VALUES ('UserGroupBlock', 'User group settings', 'UGS', 'active') RETURNING product_blocks.product_block_id`
    ```

- new resource type:

    > <u>**Create resource types**</u><br>
    Supply description for new resource type <span style="color:magenta">group_name</span>: Unique name of user group
    ```sql
    2022-10-27 11:45:10 [debug] generated SQL [orchestrator.cli.domain_gen_helpers.helpers] sql_string=INSERT INTO resource_types (resource_type, description) VALUES ('group_name', 'Unique name of user group') RETURNING resource_types.resource_type_id
    ```

- default value for resource type per product block (necessary for adding a default value to existing instances):

    > <u>**Create subscription instance values**</u><br>
    Supply default subscription instance value for resource type <span style="color:magenta">group_name</span> and product block **UserGroupBlock**: group
    ```sql
    2022-10-27 11:45:10 [debug] generated SQL [orchestrator.cli.domain_gen_helpers.resource_type_helpers] sql_string=
                    WITH subscription_instance_ids AS (
                        SELECT subscription_instances.subscription_instance_id
                        FROM   subscription_instances
                        WHERE  subscription_instances.product_block_id IN (
                            SELECT product_blocks.product_block_id
                            FROM   product_blocks
                            WHERE  product_blocks.name = 'UserGroupBlock'
                        )
                    )

                    INSERT INTO
                        subscription_instance_values (subscription_instance_id, resource_type_id, value)
                    SELECT
                        subscription_instance_ids.subscription_instance_id,
                        resource_types.resource_type_id,
                        'group'
                    FROM resource_types
                    CROSS JOIN subscription_instance_ids
                    WHERE resource_types.resource_type = 'group_name'
    ```

Last part generates the migration with the generated SQL:
```text
Generating migration file
2022-10-27 11:45:10 [info] Version Locations [orchestrator.cli.database] locations=/home/tjeerddie/projects_surf/example-orchestrator/migrations/versions/schema /home/tjeerddie/projects_surf/example-orchestrator/.venv/lib/python3.10/site-packages/orchestrator/migrations/versions/schema
  Generating /home/tjeerddie/projects_surf/example-orchestrator/migrations/versions/schema/2022-10-27_a8946b2d1647_test.py ...  done
Migration generated. Don't forget to create a database backup before migrating!
```

If you are running with `--test`, the SQL file will not be generated.

### migrate-workflows

The `main.py db migrate-workflows` command creates a migration file based on
the difference between de worfklows code and the workflows that are registered
in the database.     

Arguments

message - Migration name [default: None] [required]

Options

--test | --no-test - Optional boolean if you don't want to generate a 
migration file [default: no-test]

### revision

The `main.py db revision` command creates a new Alembic revision file.

Arguments

--message - The revision message [default: None]  
--version-path - Specify specific path from config for version file 
[default: None]  
--autogenerate | --no-autogenerate - Detect schema changes and add 
migrations [default: no-autogenerate]  
--head - Determine the head you need to add your migration to. [default: None]  

### upgrade

The `main.py db upgrade` command will upgrade the database to the specified
revision

Arguments

revision - Rev id to upgrade to [default: none]

## generate

Generate products, workflows and other artifacts.

Products can be described in a YAML configuration file which makes it easy to
generate product and product block domain models, and skeleton workflows and
unit tests. Note that this is a one time thing, the generate commands do not
support updating existing products, product-blocks, workflows and migrations.
But it does however help in defining new products with stakeholders, will
generate code that conforms to current workfloworchestrator coding BCP, and
will actually run (although limited in functionality of course).

After describing a new product in a configuration file, the following commands
are typically run:

```shell
python main.py generate product-blocks
python main.py generate products
python main.py generate workflows
python main.py generate migratrion
```

An example of a simple product configuration:

```yaml
config:
  create_summary_forms: true
name: node
type: Node
tag: NODE
description: "Network node"
fixed_inputs:
  - name: node_rack_mountable
    type: bool
    description: "is node rack mountable"
  - name: node_vendor
    type: enum
    description: "vendor of node"
    enum_type: str
    values:
      - "Cisco"
      - "Nokia"
product_blocks:
  - name: node
    type: Node
    tag: NODE
    description: "node product block"
    fields:
      - name: node_name
        description: "Unique name of the node"
        type: str
        required: provisioning
        modifiable:
      - name: node_description
        description: "Description of the node"
        type: str
        modifiable:
      - name: ims_id
        description: "ID of the node in the inventory management system"
        type: int
        required: active
```

Next we will describe the different sections in more detail:

**`config` section**

This section sets some global configuration, applicable for most workflows.

```yaml
config:
  create_summary_forms: true
```

- `create_summary_forms` indicates if a summary form will be generated in the
  create and modify workflows, currently always `true`.

**`fixed_inputs` section**

In this section we define a list of fixed inputs for a product.

```yaml
fixed_inputs:
  - name: node_rack_mountable
    type: bool
    description: "is node rack mountable"
  - name: node_vendor
    type: enum
    description: "vendor of node"
    enum_type: str
    values:
      - "Cisco"
      - "Nokia"
```

A fixed input has a `name` and a `type` field. If the type is a primitive type
(for example: str, bool, int, UUID), then this is sufficient. In the case of
`node_vendor` we use an enum type, so we add additional fields to describe the
enumeration type and its possible values.
 
**`product_blocks` section**

In this section we define the product blocks that are part of this product.
They can be either new or refer to previously defined product blocks.

```yaml
product_blocks:
  - name: node
    type: Node
    tag: NODE
    description: "node product block"
    fields:
      - name: node_name
        description: "Unique name of the node"
        type: str
        required: provisioning
        modifiable:
      - name: node_description
        description: "Description of the node"
        type: str
        modifiable:
      - name: ims_id
        description: "ID of the node in the inventory management system"
        type: int
        required: active
```

In this example we define a product block with name `node`, type `Node`, and
tag `NODE`.  `fields` is a list of fields with a type and name. The `required`
field defines in which lifecycle state the field is required. In previous life
cycle states the field will be optional. The `modifiable` flag is to indicate
if this field can be modified in a modify workflow. And the `description` field
is used in the created migration.

### migration

The `python main.py generate migration` command creates a migration from a
configuration file.

Options

--config-file - The configuration file [default: None]  
--python-version - Python version for generated code [default: 3.9]  

### product

The `python main.py generate product` command creates a product domain model
from a configuration file.

Options

--config-file - The configuration file [default: None]  
--dryrun | --no-dryrun - Dry run [default: dryrun]  
--force - Force overwrite of existing files  
--python-version - Python version for generated code [default: 3.9]  
--folder-prefix - Folder prefix, e.g. <folder-prefix>/workflows [default: None]

### product-blocks

The `python main.py generate product-blocks` command creates product block
domain models from a configuration file.

Options

--config-file - The configuration file [default: None]  
--dryrun | --no-dryrun - Dry run [default: dryrun]  
--force - Force overwrite of existing files  
--python-version - Python version for generated code [default: 3.9]  
--folder-prefix - Folder prefix, e.g. <folder-prefix>/workflows [default: None]

### unit-tests

The `python main.py generate unit-tests` command creates unit tests from a
configuration file.

Options

--config-file - The configuration file [default: None]  
--dryrun | --no-dryrun - Dry run [default: dryrun]  
--force - Force overwrite of existing files  
--python-version - Python version for generated code [default: 3.9]  
--tdd - Force test driven development with failing asserts [default: True]

### workflows

The `python main.py generate workflows` command creates create, modify,
terminate and validate workflows from a configuration file. The
`--custom-templates` option can be used to specify a folder with custom
templates to add additional import statements, input form fields and workflow
steps to the create, modify and terminate workflows.

Options

--config-file - The configuration file [default: None]  
--dryrun | --no-dryrun - Dry run [default: dryrun]  
--force - Force overwrite of existing files  
--python-version - Python version for generated code [default: 3.9]  
--folder-prefix - Folder prefix, e.g. <folder-prefix>/workflows [default: 
None]  
--custom-templates - Custom templates folder [default: None]  

## scheduler

Access all the scheduler functions.

### force

Force the execution of (a) scheduler(s) based on a keyword.

Arguments

keyword - [required]

### run

Loop eternally and run schedulers at configured times.

### show-schedule

Show the currently configured schedule.
