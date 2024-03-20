# Docker compose installation instructions

How to run the orchestrator-core and orchestrator-core-gui with Docker
Compose is described in the steps below. The following Docker images are
used:

* [orchestrator-core](https://github.com/workfloworchestrator/orchestrator-core/pkgs/container/orchestrator-core):
  The workflow orchestrator step engine.
* [orchestrator-core-gui](https://github.com/workfloworchestrator/orchestrator-core-gui/pkgs/container/orchestrator-core-gui):
  The GUI for the orchestrator-core.
* [postgres](https://hub.docker.com/_/postgres):
  The PostgreSQL object-relational database system.
* [busybox](https://hub.docker.com/_/busybox):
  The swiss army knife of embedded linux.

### Step 1 - Prepare environment

First create the folder to hold the example orchestrator that is being build
during this workshop. Then copy the `docker-compose.yml` and
`orchestrator-core-gui.env` to control and configure the environment, and
copy a `main.py` that contains a rudimentary orchestrator application.

```shell
mkdir example-orchestrator
cd example-orchestrator
curl --remote-name https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator-beginner/main/docker-compose.yml
curl --remote-name https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator-beginner/main/orchestrator-core-gui.env
curl --remote-name https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator-beginner/main/examples/main.py
```

Commit the copied files to a local git repository:

```shell
git init --initial-branch main
git config --local user.email "you@example.com"
git config --local user.name "Your Name"
git add .
git commit -m "Initial commit"
```

Note that your local git repository must contain at least one commit because
otherwise the database initializations step below will fail.

### Step 2 - Start environment

Docker compose will take care of all necessary initialization and startup of
the database, orchestrator and GUI:

1. the busybox container creates the folder `db_data`, if not yet present
2. then a postgres container creates a database, if it does not exist
   already, after which the database server is started
3. an orchestrator container is used to initialize the database, if
   not already initialized, and creates an `alembic.ini` file and a
   `migrations` folder for the database migrations
4. a second run of the orchestrator container will upgrade the database to
   the latest heads, and will do so everytime the environment is started
5. then a third run of the orchestrator container will use `main.py` to
   run the orchestrator
6. finally, the GUI is started in the orchestrator-core-gui container

```shell
docker compose up
```

### Step 3 - Open a browser

Now point a browser to:

```shell
http://localhost:3000/
```
and have a look around.

!!! note

    Once opened in the browser, ignore the message about the CRM not being
    responsive, this workshop does not include the setup of an interface to a
    CRM, fake customers IDs will be used instead.
