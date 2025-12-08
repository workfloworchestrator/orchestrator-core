# agentic_app.py

The agentic_app.py module is used in `orchestrator-core` for running the LLM enabled orchestrator.
Functionality in this class is toggled by two different environment variables:

- `SEARCH_ENABLED`: When set to `True` the orchestrator will enable the LLM Based search
- `AGENT_ENABLED`: When set to `True` the orchestrator will activate the Agent module of the orchestrator.



## FastAPI Backend

The code for the WFO's Fast API backend is very well documented, so look through the functions used in this module here:

::: orchestrator.agentic_app
    options:
        heading_level: 3
