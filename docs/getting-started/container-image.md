# Building an image

To run your orchestrator in containers, build one image with your code and run every
[process](deployment.md#processes) from it. Base it on the published
`ghcr.io/workfloworchestrator/orchestrator-core` image, which contains orchestrator-core and its
dependencies but no application code: no `main.py`, `wsgi.py`, products, workflows or migrations.

## Base image tags

Each release is published as `<version>`, e.g. `5.4.0`, and with these suffixes for optional extras:

| Suffix | Extras |
|---|---|
| `-celery` | `celery`, for [Celery workers](../guides/scaling.md) |
| `-mcp` | `mcp`, for the [MCP server](../reference-docs/mcp.md) |
| `-mcp-celery` | both |

`latest` is the newest release and `edge` the newest release or pre-release. Pin a version.

## Dockerfile

The base image has orchestrator-core in a virtual environment at `/home/orchestrator/.venv` and runs
as the `orchestrator` user in `/home/orchestrator`:

```dockerfile
FROM ghcr.io/workfloworchestrator/orchestrator-core:5.4.0-celery

# Your project: main.py, wsgi.py, alembic.ini, migrations/, products/, workflows/, translations/, ...
COPY --chown=orchestrator:orchestrator . /home/orchestrator/

# Your own dependencies, if any, into the same environment. Keep orchestrator-core at the base
# image's version.
RUN uv pip install --python /home/orchestrator/.venv/bin/python --no-cache -r requirements.txt

CMD ["python", "-m", "uvicorn", "--host", "0.0.0.0", "--port", "8080", "wsgi:app"]
```

- **The `FROM` line pins orchestrator-core.** Tag your image with your own version, e.g.
  `my-orchestrator:1.0.0`. To upgrade orchestrator-core, change the `FROM` tag, rebuild and tag a
  new version; deployments such as the [Helm chart](kubernetes.md) refer to your image's tag.
- **Run tools with `python -m`.** The environment's `bin` directory is not on `PATH`, so a bare
  `uvicorn` or `celery` is not found. The [process commands](deployment.md#processes) use
  `python -m` for that reason.
- **Commit `migrations/`.** `db init` creates it once; see
  [Preparing the source folder](prepare-source-folder.md).
- **Build for Python 3.13**, the base image's version.
- **With Celery, register the Celery app in `wsgi.py` too**; see
  [Implementing the worker](../guides/scaling.md#implementing-the-worker).

Add a `.dockerignore` for `.venv`, `.git` and other local files.
