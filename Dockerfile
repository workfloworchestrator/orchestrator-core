FROM python:3.9-slim

ARG VERSION

ENV PIP_ROOT_USER_ACTION=ignore

RUN apt-get update && apt-get install --yes git

RUN pip install pip --upgrade
RUN pip install orchestrator-core==${VERSION}

RUN useradd orchestrator
USER orchestrator
WORKDIR /home/orchestrator

CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8080", "main:app"]
