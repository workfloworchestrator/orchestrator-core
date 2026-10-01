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

Use a directory managed by trusted administrators, preferably mounted read-only for
the application. Path containment checks reject traversal and external symlinks, but
do not protect against an untrusted local writer replacing files between validation
and opening them. Only put content intended for guide readers in this directory.

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
since guide content is considered more sensitive. It uses the application's configured
authentication and authorization; disabling authentication also makes guides accessible
without credentials. It returns:

- `200` with the guide's Markdown content, if the file exists
- `404` if no guide is configured or found for that workflow name, or if the name resolves
  outside `WORKFLOW_USER_GUIDE_DIR` (including external symlinks). Missing and rejected
  guides return the same response to avoid revealing which names are external symlinks.
- `422` if `workflow_name` contains characters outside `SafeName`'s allowlist
  (`^[A-Za-z0-9._/-]+$`, from `nwastdlib.file_utils`)

`workflow_name` must fulfil `SafeName` and is a single path segment: guides are looked up
directly in `WORKFLOW_USER_GUIDE_DIR`, not in subdirectories. A request such as
`/api/workflow_user_guides/nested/guide` does not match the route and returns `404`.

The response contains a JSON string, not rendered HTML. Clients that render the Markdown
must sanitize HTML and unsafe links before displaying it.

::: orchestrator.core.services.workflow_user_guides
    options:
        heading_level: 3
