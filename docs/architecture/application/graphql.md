# GraphQL documentation

OrchestratorCore comes with a graphql interface that can to be registered after you create your OrchestratorApp.
If you add it after registering your `SUBSCRIPTION_MODEL_REGISTRY` it will automatically create graphql types for them.

example:
```python
app = OrchestratorCore(base_settings=AppSettings())
# register SUBSCRIPTION_MODEL_REGISTRY
app.register_graphql()
```

## Extending the Query and Mutation

This is an basic example of how to extend the query.
You can do the same to extend Mutation.

```python
from orchestrator.graphql import Query, Mutation


# Queries
def resolve_new(info) -> str:
    return "resolve new..."


@strawberry.federation.type(description="Orchestrator queries")
class NewQuery(Query):
    other_processes: Connection[ProcessType] = authenticated_field(
        resolver=resolve_processes,
        description="resolve_processes used for another field",
    )
    new: str = strawberry.field(resolve_new, description="new resolver")


app = OrchestratorCore(base_settings=AppSettings())
# register SUBSCRIPTION_MODEL_REGISTRY
app.register_graphql(query=NewQuery)
```
