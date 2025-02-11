# syntax=docker/dockerfile:1

# Build stage: build the wheel using an isolated build environment
FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y git build-essential
COPY . .
RUN pip install --upgrade pip
RUN pip install build
RUN python -m build --wheel --outdir dist

# Final stage: set up a lean runtime environment and install the built wheel
FROM python:3.11-slim
ENV PIP_ROOT_USER_ACTION=ignore
RUN apt-get update && apt-get install -y git
RUN pip install --upgrade pip
COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install /tmp/*.whl
RUN useradd orchestrator
USER orchestrator
WORKDIR /home/orchestrator
CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8080", "main:app"]
