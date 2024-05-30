# Installation Instructions

Here is how you can run the orchestrator-core, orchestrator-ui, and netbox with Docker Compose. We have this all
setup in our docker-compose.yml file so that you don't have to think about how to start the applications required for this workshop! If you want to read more about how to manually install the Workflow Orchestrator, please refer to [the beginner workshop here](../beginner/debian.md). The following Docker images are used in this workshop:

* [orchestrator-core](https://github.com/workfloworchestrator/orchestrator-core/pkgs/container/orchestrator-core): The workflow orchestrator step engine.
* [orchestrator-ui](https://github.com/workfloworchestrator/orchestrator-ui/pkgs/container/orchestrator-ui): The
  GUI for the orchestrator-core.
* [netbox](https://docs.netbox.dev/en/stable/): A free IPAM and SoT system.
* [postgres](https://hub.docker.com/_/postgres): The PostgreSQL object-relational database system.
* [redis](https://redis.io/): An open source, in-memory data store used by netbox
* Optional: [containerlab](https://containerlab.dev/): A free network topology simulator that uses containerized
  network operating systems.

!!! danger
    **To run the workshop with container lab, the host architecture must be x86_64 with virtualization
    enabled**


## Step 1 - Prepare environment

Ensure that you have docker and docker compose installed on your system. We won't go into deep details on how to do this as we expect you to have the knowledge to provide a working docker setup for this workshop. To make sure that docker is setup properly, run the following checks:

First, let's make sure that docker is installed:

```bash
jlpicard@ncc-1701-d:~$ docker --version
Docker version 23.0.1, build a5ee5b1dfc
```

In this case, we see that version 23.0.1 is installed, which is plenty new enough for this workshop. Any version of docker later than `19.03.0` should work for this.

Next, let's make sure that we have Docker Compose v2 setup on our machine:

```bash
jlpicard@ncc-1701-d:~$ docker compose version
Docker Compose version v2.17.2
```

!!! tip

    If this command does not work and produce a similar output, follow [the official Docker guide on installing the Docker Compose v2 plugin](https://docs.docker.com/compose/install/linux/).

### Step 2 - Start environment

Docker compose will take care of all necessary initialization and startup of
the database, orchestrator and GUI:

1. A postgres container, holding the databases for netbox and the orchestrator
2. A redis container used by netbox.
3. A set of containers spun up by netbox.
4. An orchestrator backend container that runs off main.py
5. Finally, a GUI frontend container is started.

To start all of this, simply clone the repo:

```shell
jlpicard@ncc-1701-d:~$ git clone git@github.com:workfloworchestrator/example-orchestrator.git
```

and then start the containers!

```shell
jlpicard@ncc-1701-d:~$ docker compose up -d
```

### Step 3 - Open a browser

Now point a web browser to `http://localhost:3000/` and have a look around. This is a functional orchestrator instance and represents an environment where you can perform the exercises that are part of this workshop.

!!! tip

    Once opened in the browser, ignore the message about the CRM not being responsive. This workshop does not include the setup of an interface to a CRM, fake customers IDs will be used instead.

### Helpful Items

#### Resetting Your Environment

To reset the active state of your environment back to scratch, simply use docker compose to delete volumes, like so:

```bash
jlpicard@ncc-1701-d:~$ docker compose down -v
```

You can then restart the containers as described above.

#### Accessing Netbox

Netbox can be accessed for troubleshooting and verifying that everything you have done in the workflow is working properly by pointing your web browser to `http://localhost:8000`. From there, you can login with `admin/admin`.
