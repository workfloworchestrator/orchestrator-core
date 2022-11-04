# Start orchestrator and client

### Start orchestrator

From the `beginner-workshop` folder, use Uvicorn to start the orchestrator:

```shell
uvicorn --host 127.0.0.1 --port 8080 main:app
```

Visit [the app](http://127.0.0.1:8080/api/redoc) to view the API documentation.

### Start client

From the `orchestrator-core-gui` folder, initialize your shell environment with
the variables from `.env.local` and start the client:

```
source .env.local
yarn start
```

Point a web browser to the URL `$REACT_APP_BACKEND_URL`. Once opened in the
browser, ignore the message about the CRM not being responsive, this workshop
does not include the setup of an interface to a CRM, the rest of the workshop
will use fake customers IDs.
