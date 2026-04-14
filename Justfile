# List possible recipes
default:
    @just --list

# Install/sync virtual environment with UV
sync:
    uv sync --all-groups --all-extras

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
