# Advanced Workshop Overview

## Intended audience

This workshop is intended for those who have run through the [beginner Workflow Orchestrator workshop](../beginner/overview.md), but is also accessible to those who are new to the Workflow Orchestrator. The main goal of this workshop is to introduce you to how to write orchestrator workflows that talk to external systems, as well as teaching you how to relate products to other products, using the dependency model of the Workflow Orchestrator.

!!! tip

    Knowledge of the Python programming language, Docker, and the Unix command line interface are prerequisites for this workshop.


## Topics

* **Installation**  
  Detailed instructions are given on how to prepare your environment and install the orchestrator and GUI using docker compose.
* **Start applications**  
  Outline how to start the Workflow Orchestrator backend and GUI using docker compose.
* **Create Node and Circuit Product**  
  Through a simple network node and network circuit scenario, a set of products is created showing how domain models are defined.
  * **Domain models**  
    Explains the benefits of the use of domain models and shows how the hierarchy of products, product blocks, fixed inputs and resource types are used to create product subscriptions for customers.
  * **Database migration**  
    Use the orchestrator CLI to create an Alembic database migration based on the domain models that describe the created products and product blocks.
* **Create Node and Circuit Workflows**  
  For the Node and Circuit products, we will make CREATE workflows. The use of input forms is explained as part of defining the create workflow. The Node product will introduce connecting to an external system from within a workflow, and then the Circuit workflow will build upon the existing Node subscriptions to highlight the ability to link products in the Workflow Orchestrator as dependencies. The circuit workflow will also demonstrate using the forms library to create complex objects in external systems.

## Workshop folder layout

This workshop uses the following folder layout:

```text
.
├── README.md
├── alembic.ini
├── docker
│   ├── clab
│   │   ├── configs
│   │   │   ├── ams-pcore.config
│   │   │   ├── fco-pcore.config
│   │   │   └── lhr-pcore.config
│   │   └── orch.clab.yml
│   ├── lso
│   │   ├── Dockerfile
│   │   ├── config.json
│   │   └── lso.env
│   ├── netbox
│   │   ├── configuration
│   │   │   ├── configuration.py
│   │   │   ├── extra.py
│   │   │   ├── ldap
│   │   │   │   ├── extra.py
│   │   │   │   └── ldap_config.py
│   │   │   ├── logging.py
│   │   │   └── plugins.py
│   │   ├── data.json
│   │   ├── entrypoint.sh
│   │   ├── netbox.env
│   │   ├── reports
│   │   │   └── devices.py.example
│   │   ├── scripts
│   │   │   └── __init__.py
│   │   └── setup_netbox.sh
│   ├── orchestrator
│   │   ├── entrypoint.sh
│   │   └── orchestrator.env
│   ├── orchestrator-ui
│   │   └── orchestrator-ui.env
│   ├── postgresql
│   │   └── init.sql
│   └── redis
│       └── redis.env
├── docker-compose.yml
├── main.py
├── migrations
│   ├── env.py
│   ├── helpers.py
│   ├── script.py.mako
│   └── versions
│       └── schema
│           ├── 2023-10-24_a77227fe5455_create_data_head.py
│           ├── 2023-10-27_a84ca2e5e4db_add_node.py
│           ├── 2023-11-02_c044b0da4126_add_port.py
│           ├── 2023-11-16_1faddadd7aae_add_core_link.py
│           ├── 2023-11-17_e2a0fed2a4c7_add_l2vpn.py
│           └── 2023-12-04_d946c20663d3_add_netbox_tasks.py
├── products
│   ├── __init__.py
│   ├── product_blocks
│   │   ├── __init__.py
│   │   ├── core_link.py
│   │   ├── core_port.py
│   │   ├── node.py
│   │   ├── port.py
│   │   ├── sap.py
│   │   ├── shared
│   │   │   ├── __init__.py
│   │   │   └── types.py
│   │   └── virtual_circuit.py
│   ├── product_types
│   │   ├── __init__.py
│   │   ├── core_link.py
│   │   ├── l2vpn.py
│   │   ├── node.py
│   │   └── port.py
│   └── services
│       ├── description.py
│       └── netbox
│           ├── netbox.py
│           └── payload
│               ├── core_link.py
│               ├── core_port.py
│               ├── l2vpn.py
│               ├── node.py
│               ├── port.py
│               └── sap.py
├── pyproject.toml
├── requirements.txt
├── services
│   ├── __init__.py
│   ├── lso_client.py
│   └── netbox.py
├── settings.py
├── templates
│   ├── core_link.yaml
│   ├── l2vpn.yaml
│   ├── node.yaml
│   └── port.yaml
├── translations
│   └── en-GB.json
├── utils
│   ├── __init__.py
│   └── singledispatch.py
└── workflows
    ├── __init__.py
    ├── core_link
    │   ├── create_core_link.py
    │   ├── modify_core_link.py
    │   ├── terminate_core_link.py
    │   └── validate_core_link.py
    ├── l2vpn
    │   ├── create_l2vpn.py
    │   ├── modify_l2vpn.py
    │   ├── shared
    │   │   └── forms.py
    │   ├── terminate_l2vpn.py
    │   └── validate_l2vpn.py
    ├── node
    │   ├── create_node.py
    │   ├── modify_node.py
    │   ├── modify_sync_ports.py
    │   ├── shared
    │   │   ├── forms.py
    │   │   └── steps.py
    │   ├── terminate_node.py
    │   └── validate_node.py
    ├── port
    │   ├── create_port.py
    │   ├── modify_port.py
    │   ├── shared
    │   │   ├── forms.py
    │   │   └── steps.py
    │   ├── terminate_port.py
    │   └── validate_port.py
    ├── shared.py
    └── tasks
        ├── bootstrap_netbox.py
        └── wipe_netbox.py

37 directories, 99 files

```
