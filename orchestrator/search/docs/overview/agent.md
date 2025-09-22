# Agent

The AI Search Agent is an assistant that builds and executes structured database queries to retrieve information across orchestrator entities (subscriptions, workflows, products, and processes).

Built on `pydantic-ai` and exposed via FastAPI using the `ag-ui` protocol, the agent:

- Establishes a search context (entity type and action)

- Optionally builds a validated FilterTree using discovered field paths and type-safe operators

- Executes both broad and filtered searches against the search API

Its structured query building leverages Pydantic validation to ensure queries are safe, accurate, and include feedback loops for iterative refinement.

> The [ag-ui protocol](https://docs.ag-ui.com/introduction) is a lightweight, event-based interface for connecting AI agents to user-facing applications. It enables real-time interactions, state synchronization, and tool execution between the agent and UI environments such as chat consoles or admin panels.

> The protocol is natively supported by `pydantic-ai`, allowing agents to expose tools and state without any custom wiring or logic.

---

## Architecture

### Core Components

**Agent (`agent.py`)**

- Built on `pydantic-ai` framework
- Integrates search toolset and custom instructions

**State Management (`state.py`)**

- `SearchState`: Tracks current search parameters and results
- Maintains context across tool calls
- Stores filter trees and search outcomes

**Tool System (`tools.py`)**

- **`set_search_parameters`**: Initializes search context (entity type, query)
- **`set_filter_tree`**: Builds and validates structured filters
- **`execute_search`**: Runs database queries with current parameters
- **`discover_filter_paths`**: Finds valid paths for field names
- **`get_valid_operators`**: Returns compatible operators per field type

**Instructions (`prompts.py`)**

- Base instructions: Define agent role and workflow
- Dynamic instructions: Provide context-aware next step guiding

---

## Workflow

### 1. Context Setting

```
User: "Find active subscriptions for customer SURF"
set_search_parameters(entity_type=SUBSCRIPTION, action=SELECT)
```

### 2. Filter Discovery (if needed)

```
discover_filter_paths(["status", "customer"])
Returns: subscription.status (string), subscription.customer_id (string)

get_valid_operators()
Returns: string fields support [eq, neq, like]
```

### 3. Filter Construction

```json
{
  "op": "AND",
  "children": [
    {
      "path": "subscription.status",
      "value_kind": "string",
      "condition": { "op": "eq", "value": "active" }
    },
    {
      "path": "subscription.customer_id",
      "value_kind": "string",
      "condition": { "op": "eq", "value": "SURF" }
    }
  ]
}
```

### 4. Execution

```
execute_search(limit=10)

Returns results with an answer to the users message.
```

---

## Schema Awareness & Guidance

### Pydantic-Based Validation

All tool inputs are defined using **Pydantic models**, ensuring:

- Structural correctness (e.g., required fields, value types)
- Logical validation (e.g., wildcard enforcement for `LIKE` operations)
- Automatic transformations (e.g., inferred values for `has_component` operations)

For example, the `set_filter_tree()` tool accepts a `FilterTree` model that:

- Enforces maximum nesting depth
- Validates field types against UI type mappings
- Ensures all children are either `FilterTree` or `PathFilter` instances

### Auto-Generated Tool Context

When tools are registered with the agent, their input schemas are:

- **Automatically parsed** by `pydantic-ai`
- **Summarized and injected** into the agent’s prompt context
- **Enhanced with examples** from each model’s `json_schema_extra` configuration

This allows the agent to:

- Reason about correct input shapes
- Use schema-defined examples for constructing valid tool calls
- Avoid misuse of operators, paths, or nesting structure
- Safely generate structured queries with full validation and iterative feedback loops

---

## Integration

The agent integrates with the search system through:

- **Search Functions**: Direct calls to `search_subscriptions`, `search_workflows`, etc.
- **Validation**: Uses `validate_filter_tree` for runtime schema and logic checks
- **Path discovery**: Uses the /paths endpoint for dynamic field resolution
- **Type system**: Uses the /definitions endpoint to map field types to supported operators

---

## See also

- **[Searching](searching.md)**: Search types and routing
- **[Filters](filters.md)**: Filter structure and validation
- **[Filter Operators](../reference/filter-operators.md)**: Available operators
