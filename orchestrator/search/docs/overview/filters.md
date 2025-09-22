# Filters

Structured filters let you **scope candidates** before ranking. They operate on flattened
`path:value:type` fields (see [Indexing](../architecture/indexing-flow.md)) and work with any search type (Semantic, Fuzzy, Hybrid, or Structured-only).

---

## Concept

- The root filter is a **boolean tree** (**AND/OR**) of **path predicates**.
- Each leaf targets a specific **ltree path** (e.g. `subscription.product.name`) and applies a **typed condition**.
- Paths are **type-aware**: numbers, booleans, datetimes, UUIDs, strings, and **path components** (ltree).

> Filters constrain **which entities qualify**. Ranking (scores) is applied afterwards by the selected retriever.

---

## Shapes

### FilterTree

```json
{
  "op": "AND",
  "children": [
    /* PathFilter or nested FilterTree */
  ]
}
```

### PathFilter

```json
{
  "path": "subscription.status",
  "value_kind": "string",
  "condition": { "op": "eq", "value": "active" }
}
```

- `path`: ltree path (or `*` for component-only operations)
- `value_kind`: `string | number | boolean | datetime | component` (required field specifying UI data type)
- `condition`: operator + value (see [Filter Operators](../reference/filter-operators.md))

---

## Quick examples

### 1) String + Number

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
      "path": "subscription.process.priority",
      "value_kind": "number",
      "condition": { "op": "gte", "value": 2 }
    }
  ]
}
```

### 2) Date range

```json
{
  "op": "AND",
  "children": [
    {
      "path": "subscription.start_date",
      "value_kind": "datetime",
      "condition": {
        "op": "between",
        "value": { "start": "2025-01-01", "end": "2025-02-01" }
      }
    }
  ]
}
```

### 3) Path components (ltree)

```json
{
  "op": "AND",
  "children": [
    {
      "path": "*",
      "value_kind": "component",
      "condition": { "op": "matches_lquery", "value": "subscription.*.name" }
    }
  ]
}
```

---

## Path transformation behavior

For certain component operations (`has_component`, `not_has_component`, `ends_with`), the system automatically transforms the filter when no explicit `value` is provided:

### Auto-transformation rules

```json
// Input: Using path as the target for component operations
{
  "path": "subscription.product.name",
  "value_kind": "component",
  "condition": { "op": "has_component" }
}

// Automatically transforms to:
{
  "path": "*",
  "value_kind": "component",
  "condition": { "op": "has_component", "value": "subscription.product.name" }
}
```

**When this applies:**

- Operations: `has_component`, `not_has_component`, `ends_with`
- Missing `value` in the condition
- The original `path` becomes the `value`, and `path` becomes `"*"`

This allows intuitive path-based filtering where you specify the target path directly without needing to understand the internal wildcard mechanism.

---

## Building filters

- Use **`GET /search/paths`** for path/leaf **autocomplete** (suggests leaves + components).
- Keep **operator choices** aligned to the field’s **type** (e.g., `between` only for numbers/dates).

---

## Validation

Validation makes mistakes obvious to developers, end-users in the UI and to AI agents that can auto-correct on retry.

- **PathFilter contains a typed filter** (e.g., date, number, string, ltree).
  These **filter models enforce format rules** via Pydantic (e.g., valid dates, `like` needs a wildcard, ordered ranges).

- **FilterTree checks (model-time)**

  - Max nesting depth: **5**
  - Convenience: for component ops (`has_component`, `not_has_component`, `ends_with`) without a value, the system
    moves the provided `path` into `condition.value` and sets `path="*"`.

- **Runtime checks (database-aware)**
  - Path is non-empty and **exists** in the index
  - Path starts with the correct **entity prefix** (e.g., `subscription.`) unless `path="*"`
  - Operator is **type-compatible** with the field (string/number/boolean/datetime/uuid/block/resource/component)
  - Ltree filters contain valid **PostgreSQL ltree** syntax

### Examples of validation errors

**1) Path does not exist**

```json
{
  "op": "AND",
  "children": [
    {
      "path": "subscription.nope",
      "value_kind": "string",
      "condition": { "op": "eq", "value": "x" }
    }
  ]
}
```

**Error**: "Filter path 'subscription.nope' does not exist in database schema"

**2) Wrong entity prefix (running a SUBSCRIPTION search)**

```json
{
  "op": "AND",
  "children": [
    {
      "path": "product.name",
      "value_kind": "string",
      "condition": { "op": "eq", "value": "Simple Product" }
    }
  ]
}
```

**Error**: "Filter path 'product.name' must start with 'subscription.' for SUBSCRIPTION searches."

**3) Operator not compatible with field type**

```json
{
  "op": "AND",
  "children": [
    {
      "path": "process.status",
      "value_kind": "string",
      "condition": { "op": "gte", "value": 2 }
    }
  ]
}
```

**Error**: "Filter 'NumericFilter' not compatible with field type 'string'."

**4) Invalid lquery pattern (component/path filter)**

```json
{
  "op": "AND",
  "children": [
    {
      "path": "*",
      "value_kind": "component",
      "condition": { "op": "matches_lquery", "value": "subscription.{invalid" }
    }
  ]
}
```

**Error**: "Ltree pattern 'subscription.{invalid' has invalid syntax."

**5) LIKE without wildcard**

```json
{
  "op": "AND",
  "children": [
    {
      "path": "subscription.product.name",
      "value_kind": "string",
      "condition": { "op": "like", "value": "fiber" }
    }
  ]
}
```

**Error**: "The value for a 'like' operation must contain a wildcard character ('%' or '\_')."

---

## See also

- **[Overview - Searching](searching.md)**: search types, routing rules, scoring.
- **[Reference - Operators](../reference/filter-operators.md)**: Operator matrix.

```

```
