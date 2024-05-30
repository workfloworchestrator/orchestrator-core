# Base application

By following these steps you can start a bare orchestrator application that can be used to run workflows. This
app runs as a standalone API with workflows loaded that can be run in the background. Similar to a Framework like FastAPI,
Flask and Django, you install the core library, initialise it with configuration and run. The orchestrator-core contains:

* API
* Workflow engine
* Database


!!! note
    The Orchestrator-core is designed to be installed and extended just like a FastAPI or Flask application. For more
    information about how this works read the [Reference documentation](../reference-docs/app/app.md).


### Step 1 - Install the package:
Install the core.
<div class="termy">
``` console
$ pip install orchestrator-core
---> 100%
Successfully installed orchestrator-core
```
</div>

### Step 2 - Setup the database:
Create a postgres database:

<div class="termy">
``` shell
$ createuser -sP nwa
$ createdb orchestrator-core -O nwa
```
</div>

### Step 3 - Create the main.py:
Create a `main.py` file.

``` python
from orchestrator import OrchestratorCore
from orchestrator.cli.main import app as core_cli
from orchestrator.settings import AppSettings

app = OrchestratorCore(base_settings=AppSettings())

if __name__ == "__main__":
    core_cli()
```


### Step 4 - Run the database migrations:

Initialize the migration environment.
<div class="termy">
``` console
$ PYTHONPATH=. python main.py db init
$ PYTHONPATH=. python main.py db upgrade heads
```
</div>

### Step 5 - Run the app

<div class="termy">

``` shell
$ uvicorn --reload --host 127.0.0.1 --port 8080 main:app
INFO:     Uvicorn running on http://127.0.0.1:8080 (Press CTRL+C to quit)
INFO:     Started reloader process [62967] using watchgod
ujson module not found, using json
msgpack not installed, MsgPackSerializer unavailable
2021-09-28 09:42:14 [warning  ] Database object configured, all methods referencing `db` should work. [orchestrator.db]
INFO:     Started server process [62971]
2021-09-28 09:42:14 [info     ] Started server process [62971] [uvicorn.error]
INFO:     Waiting for application startup.
2021-09-28 09:42:14 [info     ] Waiting for application startup. [uvicorn.error]
INFO:     Application startup complete.
2021-09-28 09:42:14 [info     ] Application startup complete.  [uvicorn.error]
```
</div>

### Step 6 - Profit :boom: :grin:

Visit [the app](http://127.0.0.1:8080/api/redoc) to view the api documentation.
