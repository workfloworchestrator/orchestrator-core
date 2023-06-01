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
├── docker-compose.yml
├── docs
│   ├── advanced_workshop.png
│   └── orch_advanced_workshop_architecture.png
├── etc
│   └── ...
├── main.py
├── migrations
│   └── ...
├── products
│   ├── product_blocks
│   │   ├── circuit.py
│   │   ├── node.py
│   │   ├── user.py
│   │   └── user_group.py
│   └── product_types
│       ├── circuit.py
│       ├── node.py
│       ├── user.py
│       └── user_group.py
├── requirements.txt
├── utils.py
└── workflows
    ├── circuit
    │   ├── create_circuit.py
    │   ├── modify_circuit.py
    │   ├── shared.py
    │   ├── terminate_circuit.py
    │   └── validate_circuit.py
    ├── node
    │   ├── create_node.py
    │   └── validate_node.py
    └── shared.py
```
