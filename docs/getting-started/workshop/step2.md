# Step 2 - Running the orchestrator-core-gui

The GUI application is a ReactJS application that can be run in front of the application. It will consume the API and
enable the user to interact with the products, subscriptions and processes that are built and run in the orchestrator.

The GUI is uses [Elastic-UI](https://elastic.github.io/eui/#/) as framework for standard components and [Uniforms](https://uniforms.tools/)
to parse JSON-Schema produced by the forms endpoints in the core and render the correct components and widgets.

### Clone the client repository
<div class="termy">
``` console
$ git clone https://github.com/workfloworchestrator/orchestrator-core-gui.git
```
</div>

### Install the node modules and setup the environment

The orchestrator client gui has a number of prerequisites:

- Node 14.15.0
- yarn 1.22.11


<div class="termy">
``` console
$ yarn install
$ cp .env.local.example .env.local
$ source .env.local
$ cd src
$ ln -s custom-example custom
$ yarn start
```
</div>

!!! info
    The `custom-example` directory contains some SURF specific modules that can be used as an example. It must be linked
    to let the app startup
