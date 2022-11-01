# CLI

CLI commands


## db migrate-domain-models command

The purpose of this CLI script is to automatically generate the data migrations that you'll need when you add or change a Domain Model.
It will inspect your DB and the existing domain models, analyse the differences and it will generate an Alembic data migration in the correct folder.

Features:
- detect a new Domain Model attribute / resource type
- detect a renamed Domain Model attribute / resource type
- detect a removed Domain Model attribute / resource type
- detect a new Domain Model
- detect a removed Domain Model
- ability to ask for human input when needed
- Below in the documentation these features are discussed in more detail.

BACKUP DATABASE BEFORE USING THE MIGRATION!.

### Args:
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

### Example

You need products in the `SUBSCRIPTION_MODEL_REGISTRY`, for this example I will use these models (taken out of [example-orchestrator](https://github.com/hanstrompert/example-orchestrator)):
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
- rename of fixed input input (renaming `affiliation` to `affiliationing` in User Product):
    ``` bash
    --- UPDATE FIXED INPUT DECISIONS ('N'= create and delete) ---
    rename fixed input ['affiliation'] to ['affiliationing'] for product ['User internal'] (y/N):
    ```
- rename of resource type input(renaming `age` to `user_age` in User Block), only works when the resource type is renamed in all Blocks:
    ``` bash
    --- UPDATE RESOURCE TYPE DECISIONS ('No'= create and delete) ---
    Change resource type ['age'] to ['user_age'] (y/N):
    ```

it will log the differences on info level:
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

now it will start generating the SQL, logging the SQL on debug level and prompt user for new resources:
- new product example:
    ``` bash
    --- PRODUCT ['User group'] INPUTS ---
    Product description: User group product
    Product type: UserGroup
    Product tag: GROUP
    2022-10-27 11:45:10 [debug] generated SQL [orchestrator.cli.domain_gen_helpers.helpers] sql_string=INSERT INTO products (name, description, product_type, tag, status) VALUES ('User group', 'User group product', 'UserGroup', 'GROUP', 'active') RETURNING products.product_id
    ```
- new fixed input (the type isn't checked, so typing an incorrect value will insert in db):
    ``` bash
    --- PRODUCT ['User internal'] FIXED INPUT ['affiliation'] ---
    Fixed input value: internal
    --- PRODUCT ['User external'] FIXED INPUT ['affiliation'] ---
    Fixed input value: external]
    2022-10-27 11:45:10 [debug] generated SQL [orchestrator.cli.domain_gen_helpers.helpers] sql_string=INSERT INTO fixed_inputs (name, value, product_id) VALUES ('affiliation', 'internal', (SELECT products.product_id FROM products WHERE products.name IN ('User internal'))), ('affiliation', 'external', (SELECT products.product_id FROM products WHERE products.name IN ('User external')))
    ```
- new product block:
    ``` bash
    --- PRODUCT BLOCK ['UserGroupBlock'] INPUTS ---
    Product block description: User group settings
    Product block tag: UGS
    2022-10-27 11:45:10 [debug] generated SQL [orchestrator.cli.domain_gen_helpers.helpers] sql_string=INSERT INTO product_blocks (name, description, tag, status) VALUES ('UserGroupBlock', 'User group settings', 'UGS', 'active') RETURNING product_blocks.product_block_id
    ```
- new resource type:
    ``` bash
    --- RESOURCE TYPE ['group_name'] ---
    Resource type description: Unique name of user group
    2022-10-27 11:45:10 [debug] generated SQL [orchestrator.cli.domain_gen_helpers.helpers] sql_string=INSERT INTO resource_types (resource_type, description) VALUES ('group_name', 'Unique name of user group') RETURNING resource_types.resource_type_id
    ```
- default value for resource type per product block (necessary for adding a default value to existing instances):
    ``` bash
    Resource type ['group_name'] default value for block ['UserGroupBlock']: group
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
``` bash
--- GENERATING SQL MIGRATION FILE ---
2022-10-27 11:45:10 [info] Version Locations [orchestrator.cli.database] locations=/home/tjeerddie/projects_surf/example-orchestrator/migrations/versions/schema /home/tjeerddie/projects_surf/example-orchestrator/.venv/lib/python3.10/site-packages/orchestrator/migrations/versions/schema
  Generating /home/tjeerddie/projects_surf/example-orchestrator/migrations/versions/schema/2022-10-27_a8946b2d1647_test.py ...  done
--- MIGRATION GENERATED (DON'T FORGET TO BACKUP DATABASE BEFORE MIGRATING!) ---
```

when using `--test` it will instead show:
``` bash
--- TEST DOES NOT GENERATE SQL MIGRATION ---
```
