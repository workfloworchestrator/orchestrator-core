# Prepare source folder

## Folder layout

The suggested folder layout of your own orchestrator implementation is as
follows:

```text
.
├── migrations
│   └── versions
│       └── schema
├── products
│   ├── product_blocks
│   └── product_types
├── translations
└── workflows
```

Some of the orchestrator-core functionality relies on the source folder being a
valid Git repository.

### Migrations folder and local Alembic head

The `migrations` folder is created when running `python main.py db init`.
This folder is used to store the local Alembic database migrations.
The orchestrator-core package also contains Alembic database migrations, the Alembic head in the core is labeled `schema`.
The local Alembic head should be labeled `data`.

When you already have product(s), workflow(s) or product template(s) defined,
the local Alembic head can be created by running either `python main.py db
migrate-domain-models`, `python main.py db migrate-workflows`, or `python
main.py generate migration`, these commands will detect a missing `data` head
and will add one automatically.  Please refer to the command-line documentation
for more information on these commands.

Or a handcrafted local migration can be added to the
`migrations/versions/schema` folder using the following as template:

```text
"""Create data head.

Revision ID: 9cbc348cc1dc
Revises:
Create Date: 2023-10-19T10:51:44.368621

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9cbc348cc1dc"
down_revision = None
branch_labels = ("data",)
depends_on = "da5c9f4cce1c"


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
```

The `depends_on` version ID should point to the current `schema` head.

To check the correct configuration of the local Alembic head, run the follwoing
command:

```shell
python main.py db heads
```

The output should be similar to this (except for the version ID's):

```text
27571992ebfb (data) (head)
da5c9f4cce1c (schema) (effective head)
```

Or have a look at the Alembic migration version history with:

```shell
python main.py db history
```

That will display somthing like this:

```text
<base> (da5c9f4cce1c) -> 9cbc348cc1dc (data), Create data head.
165303a20fb1 -> da5c9f4cce1c (schema) (effective head), Add subscription metadata to fulltext search index.
a09ac125ea73 -> 165303a20fb1 (schema), customer_id to VARCHAR.
b1970225392d -> a09ac125ea73 (schema), Add throttling to refresh_subscriptions_view trigger.
e05bb1967eff -> b1970225392d (schema), Add subscription metadata workflow.
bed6bc0b197a -> e05bb1967eff (schema), Add Subscriptions search view.
19cdd3ab86f6 -> bed6bc0b197a (schema), rename_parent_and_child_block_relations.
6896a54e9483 -> 19cdd3ab86f6 (schema), fix_parse_websearch.
3c8b9185c221 -> 6896a54e9483 (schema), Add product_block_relations.
3323bcb934e7 -> 3c8b9185c221 (schema), Add task_validate_products.
a76b9185b334 -> 3323bcb934e7 (schema), Fix tsv triggers.
c112305b07d3 -> a76b9185b334 (schema), Add generic workflows to core.
<base> -> c112305b07d3 (schema), Initial schema migration.
```

### Products, workflows and translations folders

The `products`, `workflows` and `translations` folders are either created by
hand, or when the `python main.py generate --help` commands are used in
combination with product templates, will be created automatically.
