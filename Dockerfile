FROM python:3.11-slim

ENV PIP_ROOT_USER_ACTION=ignore

RUN apt-get update && apt-get install --yes git

RUN pip install --upgrade pip

WORKDIR /tmp/orchestrator-core
COPY . .
RUN pip install .
RUN pip uninstall setup-tools -y

RUN useradd orchestrator
USER orchestrator
WORKDIR /home/orchestrator

CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8080", "main:app"]
