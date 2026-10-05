# Workflow Designer

The workflow designer composes new **task** workflows at runtime from `@step` functions that already exist in
your code. A designed workflow needs no code change and no database migration of its own: it is a normal row in the
`workflows` table plus a definition in `workflow_designer_definitions`, which holds its initial form fields and
the ordered list of steps it runs. Users design workflows in the Orchestrator UI; it talks to the REST API described
below.

The designer is aimed at script-like tasks: look something up, check it, log the result, ask a user to confirm.
It does not create or terminate subscriptions.

## Enabling the designer

The API is mounted at `/api/workflow-designer` when `WORKFLOW_DESIGNER_ENABLED` is set:

```python
from orchestrator.core.settings import app_settings

app_settings.WORKFLOW_DESIGNER_ENABLED = True
```

The setting only controls the API. Workflows that were designed earlier keep running and listing when it is off,
because every process resolves them through `get_workflow` (see [How designed workflows run](#how-designed-workflows-run)).

| Setting | Default | Meaning |
|---|---|---|
| `WORKFLOW_DESIGNER_ENABLED` | `False` | Mount the designer API. |
| `WORKFLOW_DESIGNER_NAME_PREFIX` | `"designed_"` | Every designed workflow name starts with this prefix, so it can never shadow a workflow from code. Do not change it once workflows exist. |
| `WORKFLOW_DESIGNER_STEP_PACKAGES` | `["orchestrator.core.workflows"]` | Packages whose module level steps the designer offers. |

## Offering your own steps

Register your workflows package once at startup, for example where you load your workflows:

```python
from orchestrator.core.workflow_designer.discovery import register_step_package

register_step_package("my_orchestrator.workflows")
```

The designer imports every module in the configured packages and collects each module level `Step`. A step is
addressed as `module:attribute`, because step names and function names are often reused. Steps that only exist
inside a factory or a `conditional`/`step_group` wrapper have no such address and are not offered.

The interface of a step is inferred from its code:

- **Inputs** come from the function signature: the parameter names are the state keys it reads, and the
  annotations give their type. A parameter typed as a domain model is loaded from the database by
  `subscription_id`, so the designer restricts it to the products and lifecycles that model accepts.
- **Outputs** are read from the dict literals the function returns. Keys returned on every path are guaranteed;
  keys returned on only some paths, or values built with `**spread`, are reported but not relied upon.

Steps that read the whole `state`, take `*args`/`**kwargs`, or are input steps cannot be used: their interface cannot
be determined.

## Compatibility checks

The designer refuses a definition in which a step needs a state key that is not available at that point, or that
has an incompatible type. It simulates the state through the step list: first the engine keys and the initial form
fields, then each step's guaranteed outputs. A type that cannot be inferred is a warning, not an error.

When a missing input can be provided by a form field, the designer suggests one, and the UI adds it to the initial
form when the step is dropped.

## Initial form field types

Core offers `string`, `text`, `integer`, `boolean`, `uuid`, `choice` and `customer` fields. Applications add their own,
for example a subscription selector, with `register_field_type`:

```python
from orchestrator.core.workflow_designer.forms import FieldOptions, FieldType, register_field_type
from orchestrator.core.workflow_designer.type_refs import TypeRef

register_field_type(
    FieldType(
        "subscription",
        "Subscription",
        annotation=lambda options: my_subscription_id_type(tags=options.product_tags),
        state_type=lambda options: TypeRef(kind="subscription", product_tags=options.product_tags),
        options=["product_tags", "statuses"],
        # Offer this field for step inputs it can provide.
        suggest=lambda name, ref: FieldOptions(product_tags=ref.product_tags) if ref.kind == "subscription" else None,
    )
)
```

## Helper steps

Besides steps from code, the designer offers configurable helpers:

| Helper | Does |
|---|---|
| `designer:set_value` | Puts a fixed value in the state, for an input no form field provides. |
| `designer:log_message` | Appends a message built from state values (`"Checked {subscription_id}"`) to `designer_log`. |
| `designer:load_subscription_info` | Reads description, status, product and customer of a subscription into the state. |
| `designer:confirm` | Pauses the workflow until a user confirms. |

## Authorization

By default a designed workflow uses the application's internal authorize and retry callbacks, like core's own
tasks. To decide per workflow, set a factory that returns an authorizer for a workflow name:

```python
from orchestrator.core.workflow_designer.builder import set_authorizer_factory

set_authorizer_factory(lambda name: my_task_authorizer(name))
```

## How designed workflows run

`get_workflow` falls back to *workflow sources* for names that are not registered in code with a
`LazyWorkflowInstance`. The designer registers a source that loads a designed workflow from the database and builds
it, so the API, workers, the scheduler and the CLI all resolve designed workflows without further configuration.
Applications can register their own source with `register_workflow_source`.

Built workflows are cached per process and rebuilt when the stored definition changes. A definition cannot be
changed or deleted while the workflow has unfinished processes, because a resumed process continues at a step
position. Deleting a workflow that has process history archives it instead, so its processes stay readable.

## REST API

| Method and path | Purpose |
|---|---|
| `GET /info` | The name prefix and number of available steps. |
| `GET /steps?rescan=` | All steps and helpers, with inputs, outputs and usability. |
| `GET /field-types` | Initial form field types. |
| `POST /validate` | Check a definition; with `insert_at`, also report which steps fit at that position. |
| `GET /workflows`, `POST /workflows` | List and create designed workflows. |
| `GET`, `PUT`, `DELETE /workflows/{name}` | Read, update and delete (or archive) one. |

## Limitations

- Designed workflows have no translations; their description is the one stored in the database.
- Workflows are linear: there are no conditional steps or branches.
- Side effects of steps, such as calls to external systems, are not checked.
