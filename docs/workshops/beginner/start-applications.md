# Start orchestrator and client

## Manual

### Start orchestrator

From the `example-orchestrator` folder, use Uvicorn to start the orchestrator:

```shell
uvicorn --host 127.0.0.1 --port 8080 main:app
```

If you are running without authentication set up, you can set the environment variable to false from the command line:
```
OAUTH2_ACTIVE=false uvicorn --host localhost --port 8080 main:app
```

Visit [the app](http://127.0.0.1:8080/api/docs) to view the API documentation.

### Start client

From the `example-orchestrator-ui` folder, run the following command to start the front end.
`npm run dev`

## Docker compose

Using Docker compose the only thing needed to start all application is to
run:

```shell
docker compose up
```

And point a browser to `http://localhost:3000/`.

!!! note

    Once opened in the browser, ignore the message about the CRM not being
    responsive, this workshop does not include the setup of an interface to a
    CRM, fake customers IDs will be used instead.
