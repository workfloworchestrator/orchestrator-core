# LLM-enabled Orchestrator Core

__Enhance the Orchestrator's functionality by enabling LLM features, which unlock both the search and agent modules for natural language interaction.__

## Features

### Search Module
- Enables semantic and structured search across subscriptions, products, processes, and workflows
- Utilizes vector embeddings for powerful search capabilities
- Works with or without LLM integration

### Agent Module
- Enables natural language interaction with the Orchestrator
- Supports complex queries and operations through conversational interfaces

!!! danger "Experimental Features"
    The features and APIs described in this section are under active development and may change.

    **Note:** While these features are experimental, they unlock significant potential for advanced use cases.

## Quick Start

### Prerequisites
- PostgreSQL with `pgvector` extension
- Python 3.9+
- OpenAI API key (or compatible LLM provider)
- (Optional) Configured UI for LLM integration

### 1. Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Install the package with LLM dependencies:

```bash
pip install "orchestrator-core[agent,search]"
```

### 2. Database Setup

#### Using Docker (Recommended)

```bash
docker run --name orch-db -e POSTGRES_PASSWORD=yourpassword -p 5432:5432 -d pgvector/pgvector:pg17
docker exec -it orch-db createdb -U postgres orchestrator-core
```

#### Manual Setup
1. Install PostgreSQL with pgvector
2. Create a database and user:
   ```sql
   CREATE USER nwa WITH PASSWORD 'yourpassword';
   CREATE DATABASE orchestrator-core OWNER nwa;
   ```

### 3. Configuration

Create a `.env` file in your project root:

```env
DATABASE_URI=postgresql://nwa:yourpassword@localhost:5432/orchestrator-core
OPENAI_API_KEY=your_openai_api_key
AGENT_MODEL=gpt-4o-mini
SEARCH_ENABLED=true
AGENT_ENABLED=true
```

### 4. Application Setup

Create a `main.py` file.
This provides the CLI entrypoint to your Orchestrator.

```python
import typer
from nwastdlib.logging import initialise_logging
from orchestrator import app_settings
from orchestrator.cli.main import app as core_cli
from orchestrator.db import init_database
from orchestrator.log_config import LOGGER_OVERRIDES

def init_cli_app() -> typer.Typer:
    initialise_logging(LOGGER_OVERRIDES)
    init_database(app_settings)
    return core_cli()

if __name__ == "__main__":
    init_cli_app()
```

Create a `wsgi.py` file.
This will be used to run the Orchestrator API.

```python
from orchestrator import OrchestratorCore
from orchestrator.settings import app_settings
from orchestrator.llm_settings import llm_settings

app = OrchestratorCore(
    base_settings=app_settings,
    llm_settings=llm_settings,
    llm_model=llm_settings.AGENT_MODEL,
    agent_tools=[]
)
```

### 5. Database Migrations

```bash
export $(grep -v '^#' .env | xargs)
python main.py db init
python main.py db upgrade heads
```

### 6. Start the Application

```bash
uvicorn --reload --host 0.0.0.0 --port 8080 wsgi:app
```

### 7. Index Your Data

!!! warning "API Costs"
    This step makes API calls to your LLM provider and may incur costs.

```bash
# Index all available data
python main.py index all

# Or index specific types
python main.py index subscriptions
python main.py index products
python main.py index processes
python main.py index workflows
```

## Using the API

Once running, you can access:
- API Documentation: [http://localhost:8080/api/docs](http://localhost:8080/api/docs)
- ReDoc: [http://localhost:8080/api/redoc](http://localhost:8080/api/redoc)

## Next Steps

- [Create a product](../workshops/advanced/domain-models.md)
- [Create a workflow for a product](./workflows.md)
- [Generate products and workflows](../reference-docs/cli.md#generate)
- [Lookup the reference documentation](../reference-docs/app/agentic-app.md)
