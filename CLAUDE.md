# orchestrator-core — Claude Code Guide

## Project
- **Package**: `orchestrator-core` (SURF), module `orchestrator`
- **Version**: see `orchestrator/__init__.py`
- **Stack**: FastAPI, SQLAlchemy, Pydantic v2, Strawberry GraphQL, LiteLLM
- **Python**: 3.11–3.14 | **Package manager**: `uv` | **Build**: `uv`

## Common Commands
```bash
uv run pytest test/unit_tests          # unit tests
uv run pytest test/integration_tests   # integration tests
uv run mypy orchestrator               # type check
uv run ruff check orchestrator         # lint
uv run ruff format orchestrator        # format (also: black)
pre-commit run --all-files             # format, lint, type check.
```

## Code Style
- Line length: **120**
- **No relative imports** — all imports must be absolute (`ban-relative-imports = "all"`)
- Type annotations required everywhere (mypy strict)
- Docstring convention: Google style
- Formatter: black + ruff

## Code Rules
- Code shoule be as `pure` as possible with no side effects.
- Minimize loops keep it as functional as possible
- Use itertools and more_itertools when possible
- Cover all code paths, not just the happy path.
- Generate a test for every new feature
- Use best practices of important libraries: Pydantic (v2), FastAPI
- Code in the same style as the code context
- Parameterize tests as much as possible
- Write tests for edge cases
- Write tests for exceptions

## Key Directories
```
orchestrator/
  api/         REST API (FastAPI routers)
  cli/         CLI (typer/click)
  db/          SQLAlchemy models, queries, filters, sorting
  domain/      Business domain models (subscriptions, products, blocks)
  graphql/     Strawberry GraphQL schema & resolvers
  search/      LLM search subsystem
  services/    Business logic services
  workflows/   Workflow DSL & execution engine
  websocket/   Real-time WebSocket support
  app.py       Core FastAPI application
test/
  unit_tests/
  integration_tests/
  acceptance_tests/
docs/
  reference-docs/  Refernce documentation a bit outdated but still useful
  architecture     Application architecure
```

## Optional Extras
- `search` extra: adds LiteLLM for search
- `celery` extra: adds Celery worker support

## Test Markers
- `workflow` — full workflow tests (slow)
- `acceptance` — acceptance tests (special handling)
- `search` — requires search extra
- `celery` — requires celery

## Commit Messages
- Add descriptive messages
- Don't add Co-Authored-By Claude
