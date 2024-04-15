# app.py

The app.py module is used in `orchestrator-core` for actually running the entire WFO FastAPI backend and the CLI.

## FastAPI Backend

The code for the WFO's Fast API backend is very well documented, so look through the functions used in this module here:

::: orchestrator.app
    options:
        heading_level: 3

A great example of how to use the functions available in app.py with your own `main.py` when you instantiate your own instance of the orchestrator can be seen in the [example orchestrator repository's](https://github.com/workfloworchestrator/example-orchestrator/blob/master/main.py) `main.py` file.

```python
{% include 'https://raw.githubusercontent.com/workfloworchestrator/example-orchestrator/master/main.py' %}
```

## CLI App

The orchestrator core also has a CLI application that is documented in [detail here](../cli.md). You can bring this into your `main.py` file so that you can run the orchestrator CLI for development like so:

```python
if __name__ == "__main__":
    core_cli()
```
