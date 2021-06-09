# Bare application

By following these steps you can start a bare orchestrator-core application that can be used to run workflows.


## Initialization steps
This project can be installed as follows:

#### Step 1 - Install the package:
Install the core.
```console
pip install orchestrator-core
```

#### Step 2 - Setup the database:
Create a postgres database:
```console
createuser -sP nwa
createdb orchestrator-core -O nwa
```

#### Step 3 - Create the main.py:
Create a `main.py` file.

```python
from orchestrator import OrchestratorCore
from orchestrator.cli.main import app as core_cli
from orchestrator.settings import AppSettings

app = OrchestratorCore(base_settings=AppSettings())

if __name__ == "__main__":
    core_cli()
```

#### Step 4 - Run the database migrations:
Initialize the migration environment.
```console
PYTHONPATH=. python main.py db init
PYTHONPATH=. python main.py db upgrade heads
```

### Step 5 - Profit :):

```console
uvicorn --reload --host 127.0.0.1 --port 8080 main:app
```

Visit [http://127.0.0.1:8080/api/redoc](http://127.0.0.1:8080/api/redoc) to view the api documentation.
