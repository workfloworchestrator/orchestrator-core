# The Orchestrator Shell

For different reasons, it could be that incorrect information somehow ends up in the Orchestrator database. For the
(few) users that are aware of the database model of Workflow Orchestrator, a last resort could be to fix this with
hand-written SQL queries. For obvious reasons, this is error-prone and not a safe way of interacting with your
subscription database. To help with this issue, there is the Orchestrator Shell. The Orchestrator Shell provides an
easy way to navigate and edit subscriptions, product blocks, processes, and resource types.

!!! Danger

    The shell operates **directly** on the database, and changes made are instantly committed to the database. While
    using the shell, try to avoid other write access to the database, or at least limit write access to the information
    you are touching. Also note that none of the information that is updated in the database is checked syntactically
    or in any other way, except for the `insync`, `start_date` and `end_date` subscription fields, these fields will
    not allow syntactically incorrect values.  Updating information in the database with unsupported values may break
    things. *Use this shell at your own risk.*

!!! Note

    Only scalar resource types are supported. All non-scalar resource types are shown as `<unset or non-scalar>` while
    they can have a value in the database. Optional yet unset resource types can be assigned a value with the
    `resource_type  update` command, but do not try to update non-scalar resource types using the `orchestrator_shell`.

## Installation

There are three ways of running Orchestrator Shell, and the best option will vary per deployment of WFO.

### Running using `uv`

The quickest option is to run the following command in a terminal window:

```shell
uvx orchestrator-shell
```

This will install any required dependencies for Orchestrator Shell, and connect to your subscription database. This does
however require the database URI to be available in your shell environment as `DATABASE_URI`, which is the same for WFO.

### Running Inside Your WFO Installation

The second option is to install `orchestrator-shell` inside an existing deployment of your orchestrator. How to do this
will depend on how your orchestrator is deployed. For example, when your orchestrator runs from a Docker container, the
way to install would be to open a terminal session inside your container using
`docker exec -it <my_orchestrator_container> orchestrator-shell`.

For this option, since Orchestrator Shell will run in the same environment as your Orchestrator, no configuration is
required for the Orchestrator Shell to connect to your subscription database.

#### Bundling It With Your Own Orchestrator

To prevent having to re-install Orchestrator Shell each time your application has restarted, you could bundle the
Orchestrator Shell with your own orchestrator. This can be done by simply running `uv add orchestrator-shell` in your
orchestrator project, and building a new version of your application.

## Usage

The Orchestrator Shell can be used to manipulate subscription instances and processes.

### Updating a Subscription

To update the value of an attribute of an existing subscription, use the following commands:

```shell
subscription search <search_term>
subscription select <index>
subscription
product_block list
product_block select <index>
resource_type list
resource_type select <index>
resource_type update <new_value>
```

### Updating a Process

The only operation supported on processes is leapfrogging. This can be useful when a step is continuously failing for
reasons that lie outside of the orchestrator. For example, an interaction with an external system could be
malfunctioning. When using the leapfrog command, the currently failed step is forcefully marked as a success, and the
workflow can be retried to continue from the next step in the step list. This can be done using:

```shell
process list
[process search <term>]
process select <index>
process leapfrog
```
