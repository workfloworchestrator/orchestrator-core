# Workflow User Guides

Orchestrator can serve a Markdown guide alongside a workflow, for operators who need
instructions on how to run it or what to expect. This mirrors the way
[translations](../../getting-started/prepare-source-folder.md#pointing-the-orchestrator-at-your-translations-folder)
are served: a directory of files is pointed to by an application setting, and a REST
endpoint reads the file matching the requested name.

## Configuring the guide directory

Set `WORKFLOW_USER_GUIDE_DIR` in your application settings to the directory that holds
your guide files:

```python
from pathlib import Path
from orchestrator.core.settings import app_settings

app_settings.WORKFLOW_USER_GUIDE_DIR = Path("docs/workflow-guides")
```

If `WORKFLOW_USER_GUIDE_DIR` is `None` (the default), the endpoint returns `404` for
every workflow.

## Guide file layout

Each guide is a single Markdown file, named after the workflow it documents:

```
docs/workflow-guides/
├── create_l2vpn.md
├── modify_l2vpn.md
└── terminate_l2vpn.md
```

`get_workflow_guide(workflow_name)` reads `{WORKFLOW_USER_GUIDE_DIR}/{workflow_name}.md`
as UTF-8 text and returns its contents, or `None` if the directory isn't configured or
the file doesn't exist. Workflows without a corresponding file simply have no guide.

## REST endpoint

The guide is served at:

```
GET /api/workflow_user_guides/{workflow_name}
```

This endpoint requires authentication, unlike the public `/api/translations` endpoint,
since guide content is considered more sensitive. It returns:

- `200` with the guide's Markdown content, if the file exists
- `404` if no guide is configured or found for that workflow name
- `422` if `workflow_name` doesn't match the expected pattern (`^[a-z][a-z0-9_]*$`)

::: orchestrator.core.services.workflow_user_guides
    options:
        heading_level: 3
