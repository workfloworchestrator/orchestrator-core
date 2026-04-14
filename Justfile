# List possible recipes
default:
    @just --list

# Install/sync virtual environment with UV
sync:
    uv sync --all-groups --all-extras

# Run unit tests with pytest. Support service in docker/pytest/docker-compose.yaml will be started
[env("CACHE_URI", "redis://:nwa@localhost"), env("DATABASE_URI", "postgresql://nwa:nwa@localhost/nwa")]
pytest *pytest_args:
    @just sync
    @just pytest-support-start
    uv run pytest {{pytest_args}}


# Start pytest support services from docker/pytest/docker-compose.yaml
pytest-support-start:
    (cd docker/pytest-support; docker compose up --wait)

# Cleanup pytest support services from docker/pytest/docker-compose.yaml
pytest-support-clean:
    (cd docker/pytest-support; docker compose down --volumes)

# Serve orchestrator-core docs with live-reload
docs-preview:
    @just sync
    uv run mkdocs serve

# Run pre-commit on all files
pre-commit:
    uv run pre-commit run --all-files

# Install pre-commit script into .git/hooks/pre-commit
pre-commit-install:
    uv run pre-commit install
