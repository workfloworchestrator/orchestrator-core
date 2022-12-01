FROM python:3.9-slim

ENV PIP_ROOT_USER_ACTION=ignore

#RUN apt-get update && apt-get upgrade --yes && apt-get install --yes git
RUN apt-get update && apt-get install --yes git

RUN pip install pip --upgrade
RUN pip install orchestrator-core

RUN useradd orchestrator
USER orchestrator
WORKDIR /home/orchestrator

CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8080", "main:app"]
