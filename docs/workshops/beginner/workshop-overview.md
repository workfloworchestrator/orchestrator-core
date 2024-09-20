# Beginner Workshop Overview

## Intended audience

This workshop is intended for everybody who is new to the workflow orchestrator
and wants to learn how to install and run the applications, and create a first
working set of products and associated workflows.

Knowledge of the Python programming language and the Unix command line interface
are prerequisites to do this workshop.

## Topics

* **Installation**  
  Detailed instructions are given on how to prepare your environment and
  install the orchestrator and GUI. Instructions for both Debian and MacOS are
  included.
* **Start applications**  
  Shows a simple way of starting the orchestrator and GUI.
* **Create User and User Group products**  
  Through a simple user and group management scenario a set of products is
  created showing how domain models are defined.
    * **Domain models**  
       Explains the benefits of the use of domain models and shows how the
       hierarchy of products, product blocks, fixed inputs and resource
       types is used to create product subscriptions for customers.
     * **Database migration**  
      Use the orchestrator to create an Alembic database migration based on the
      domain models that describe the created products and product blocks.
* **Create User and User Group workflows**  
  For both the User And User Group products a set of create, modify and
  terminate workflows will be created. The use of input forms is explained
  as part of defining the create workflow. This will show how a simple
  product block hierarchy is created.


During this workshop a set of products will be created together with the needed
workflows to administer users and user groups. The products will be just
complex enough to show the basic capabilities of products, product blocks,
fixed inputs, resource types and workflows in the workflow orchestrator.

The following user and user group attributes will be stored:

* **UserGroup**
    * **group_name**: name of the user group
    * **group_id**: ID of the group in an imaginary group management system
* **User**
    * **affiliation**: the user's affiliation (**internal** or **external**)
    * **username**: name of the user
    * **age**: age of the user
    * **user_id**: ID of the user in an imaginary user management system
    * **group**: group the user belongs to

## Workshop folder layout

This workshop uses the following folder layout:

```text
beginner-workshop
│
├── example-orchestrator
│   ├── main.py
│   ├── migrations
│   │   └── ...
│   ├── products
│   │   ├── __init__.py
│   │   ├── product_blocks
│   │   │   ├── user.py
│   │   │   └── user_group.py
│   │   └── product_types
│   │       ├── user.py
│   │       └── user_group.py
│   └── workflows
│       ├── __init__.py
│       ├── user
│       │   ├── create_user.py
│       │   ├── modify_user.py
│       │   └── terminate_user.py
│       └── user_group
│           ├── create_user_group.py
│           ├── modify_user_group.py
│           └── terminate_user_group.py
│
└── orchestrator-core-gui
    └── ...
```

The `example-orchestrator-ui` folder will be cloned from GitHub. The
`example-orchestrator` folder will be used for the orchestrator that is created
during this workshop.  Although any layout of the latter folder will work, it
is encouraged to use the suggested folder layout and filenames during this
workshop.
