# The Orchestrator web interface

As part of the Workflow Orchestrator setup it's possible to run a web interface. An example of how to setup the web interface is provided in the [Example orchestrator UI][1] repository. It works 'out-of-the-box' with a standard Workflow orchestrator engine and can be expanded with extra fields and pages and customized with your branding. It shows an example local development setup.

### Short overview

The Orchestrator UI is based on the [NextJS framework][2] which in turn is based on [React][3]. It uses the [Orchestrator UI component library][4] NPM package to provide most of the functionality. The [Example orchestrator UI][1] repository shows how to provide configuration and customization.

### Prerequisites:

Before running an installation of the Workflow Orchestrator UI make sure to have these installed

```
- NodeJS, version > 21
- npm
- A git client
```

### Installation

Clone the example UI repository:

```
mkdir orchestrator-ui
cd orchestrator-ui
git clone https://github.com/workfloworchestrator/example-orchestrator-ui .
```

Install the npm packages:

```
npm i
```

Set the correct env variables.
To run the UI against the dockerized example orchestrator setup, it's recommended to use the `orchestrator-ui.env` env-file.

```
wget -O .env https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/refs/heads/master/docker/orchestrator-ui/orchestrator-ui.env
```

Run the application:

```
npm run dev
```

The Orchestrator UI now runs on http://localhost:3000



[1]: https://github.com/workfloworchestrator/example-orchestrator-ui
[2]: https://nextjs.org
[3]: https://react.dev
[4]: https://www.npmjs.com/package/@orchestrator-uiorchestrator-ui-components
[5]: https://workfloworchestrator.org/orchestrator-core/architecture/application/workflow
[6]: https://nextjs.org/docs/pages
[7]: https://nextjs.org/docs/app/building-your-application/routing
[8]: https://github.com/workfloworchestrator/orchestrator-ui-library
