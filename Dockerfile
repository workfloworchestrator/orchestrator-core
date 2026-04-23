# Pin uv to a specific version so builds are reproducible
FROM ghcr.io/astral-sh/uv:0.11.5 AS uv_image

###############
### Build stage
FROM python:3.13-slim AS build
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY . .

RUN --mount=from=uv_image,source=/uv,target=/bin/uv \
    uv build --wheel --out-dir dist

###############
### Final stage
FROM python:3.13-slim

# Prevent uv from downloading Python, use the one already in this image
ENV UV_PYTHON_DOWNLOADS=never
# Set pythonpath so that activating the venv is not required
ENV PYTHONPATH=/home/orchestrator/.venv/lib/python3.13/site-packages

# git may be required at deploy time to install dependencies from github
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv_image /uv /usr/local/bin/uv
RUN useradd -m orchestrator
WORKDIR /home/orchestrator

COPY --from=build /app/dist/*.whl /tmp/
# Pre-create the project venv and install orchestrator-core into it.
# When the example-orchestrator entrypoint runs `uv sync` from this WORKDIR it will find the
# existing .venv and only add additional dependencies on top.
RUN uv venv .venv \
    && uv pip install --python .venv/bin/python /tmp/*.whl --no-cache \
    && chown -R orchestrator:orchestrator .venv

USER orchestrator

EXPOSE 8080
CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8080", "wsgi:app"]
