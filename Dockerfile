# Build stage
FROM python:3.11-slim AS build
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN pip install --upgrade pip --no-cache-dir
RUN pip install build --no-cache-dir
RUN python -m build --wheel --outdir dist

# Final stage
FROM python:3.11-slim
ENV PIP_ROOT_USER_ACTION=ignore
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip --no-cache-dir
COPY --from=build /app/dist/*.whl /tmp/
RUN pip install /tmp/*.whl --no-cache-dir
RUN useradd orchestrator
USER orchestrator
WORKDIR /home/orchestrator
CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8080", "main:app"]
