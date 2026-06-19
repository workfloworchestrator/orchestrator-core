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

- [skip to creating a workflow](./workflows.md)

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

That will display something like this:

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

#### Translations folder

The `translations` folder holds locale files consumed by the orchestrator UI.
Each file is named after a language tag in the form `language-REGION.json`, e.g. `en-GB.json`.

```text
translations/
└── en-GB.json
```

The file contains two top-level sections:

- **`forms.fields`** — human-readable labels and helper text for form fields
  displayed in the UI.
- **`workflow`** — display names for every workflow registered in the
  orchestrator.  The key is the workflow's internal name (the value passed to
  `@workflow`) and the value is the label shown in the UI.

A minimal example:

```json
{
    "forms": {
        "fields": {
            "subscription_id": "Subscription",
            "subscription_id_info": "The subscription for this action"
        }
    },
    "workflow": {
        "create_node": "Create Node",
        "modify_node": "Modify Node",
        "terminate_node": "Terminate Node",
        "validate_node": "Validate Node"
    }
}
```

##### Merging with core translations

orchestrator-core ships its own locale files for built-in workflows and form
fields (e.g. `task_clean_up_tasks`, `note`).  At runtime, `generate_translations`
deep-merges the core file with the application's file: keys present in the
application file override core keys, and any additional keys are added on top.
This means you only need to define translations for your own products and
workflows; core translations are inherited automatically.

The merged translations are served by the REST API at:

```
GET /api/v1/translations/{language}
```

where `{language}` is a `language-REGION` tag (e.g. `en-GB`).

##### Pointing the orchestrator at your translations folder

Set `TRANSLATIONS_DIR` in your application settings to the directory that
contains your locale files:

```python
# main.py / settings
app_settings.TRANSLATIONS_DIR = Path("translations")
```

If `TRANSLATIONS_DIR` is `None` (the default) only the core translations are
served.

##### Generating translations with the CLI

When you scaffold a new product with `python main.py generate`, the generator
automatically writes four workflow keys to `translations/en-GB.json`.  The
target file can be changed by setting the `TRANSLATION_PATH` environment
variable (default: `translations/en-GB.json`):

| Key | Default value |
|---|---|
| `create_{variable}` | `Create {Name}` |
| `modify_{variable}` | `Modify {Name}` |
| `validate_{variable}` | `Validate {Name}` |
| `terminate_{variable}` | `Terminate {Name}` |

If the file does not exist yet, the generator creates it.

##### Translation validation

The built-in `task_validate_products` task checks that every workflow
registered in the orchestrator has a corresponding key in the `workflow`
section of the `en-GB` translations.  Running this task after adding a new
workflow will surface any missing keys before they cause silent UI gaps.
