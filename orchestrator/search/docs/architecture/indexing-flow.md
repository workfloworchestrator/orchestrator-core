# Indexing

## Overview

The indexer processes entities in chunks, extracts path/value pairs, manages token budgets for embedding calls, and uses content hashing for incremental updates.

1. **Chunking**: entities are read in configurable groups (default: 1000) so large datasets can be processed without exhausting memory.

2. **Field extraction**: entities are traversed into `path:value:type` records that can be indexed.

3. **Change detection**: content hashes are computed for each `path:value:type` and compared against existing records. Only new or changed fields are prepared for indexing, while stale fields are scheduled for deletion.

4. **Per-chunk batching and upsert**: within each chunk, fields are split into two buffers:
   - **Embeddable fields** (semantic strings) are tracked against a token budget. A flush occurs before exceeding the model’s context window or batch size. These fields are converted to vectors via the embedding API.
   - **Non-embeddable fields** (UUIDs, integers, booleans, datetimes) are accumulated in parallel. They don’t influence the token budget but are always flushed together with the embeddable buffer.
     Once flushed, both buffers are merged and written as a single UPSERT batch, after removing stale paths.

## Core Components

### 1. Streaming Entity Processing

The indexer reads entities from the database using `yield_per` to avoid loading large datasets into memory.

### 2. Field Traversal and Extraction

Each entity is passed to its registered traverser (see `traverse.py`).
Traversers walk the object hierarchy defined by Pydantic models and flatten it into `path:value:type` records that can be indexed.
This makes deeply nested product structures compatible with PostgreSQL’s `LTree` paths.

- **SubscriptionTraverser**: Resolves the root subscription and its linked product.
- **ProductTraverser**: Walks the product schema and its blocks.
- **Process/WorkflowTraversers**: Apply schema validation.

#### Example: Simple Subscription

```python
from uuid import UUID
from orchestrator.domain.base import SubscriptionModel, ProductModel, ProductBlockModel

class BasicBlock(ProductBlockModel):
    name: str
    value: int
    enabled: bool

class SimpleProduct(ProductModel):
    product_id: UUID
    name: str
    basic_block: BasicBlock

class SimpleSubscription(SubscriptionModel, is_base=True):
    subscription_id: UUID
    customer_id: str
    product: SimpleProduct
```

Example instance:

```python
from uuid import UUID

SimpleSubscription(
    subscription_id=UUID("abc12345-6789-0000-0000-000000000000"),
    customer_id="test-customer",
    product=SimpleProduct(
        product_id=UUID("99999999-aaaa-0000-0000-000000000000"),
        name="Simple Product",
        basic_block=BasicBlock(name="SimpleBlock", value=42, enabled=True),
    ),
)
```

Flattened traversal:

```
subscription.subscription_id             -> "abc12345-6789-0000-0000-000000000000" (UUID)
subscription.customer_id                 -> "test-customer"                        (STRING)
subscription.product.product_id          -> "99999999-aaaa-0000-0000-000000000000" (UUID)
subscription.product.name                -> "Simple Product"                       (STRING)
subscription.product.basic_block.name    -> "SimpleBlock"                          (STRING)
subscription.product.basic_block.value   -> "42"                                   (INTEGER)
subscription.product.basic_block.enabled -> "True"                                 (BOOLEAN)
```

### 3. Change Detection

The indexer uses content hashing to avoid reprocessing unchanged data:

```python
content_hash = sha256(f"{path}:{value}:{value_type}").hexdigest()
```

- Fetches existing hashes for each LTree record in the entity chunk
- Compares current vs existing hashes per field
- Only processes changed/new fields (unless `force_index=True`)

### 4. Two-Buffer Batching System

Within each chunk, extracted fields are split into two processing streams: one for fields that require embeddings and one for those that don’t.

#### Determining Embeddable Fields

Not all fields are suitable for embeddings. The indexer applies a **two-stage filter** during traversal to decide which fields to embed:

- **Type-based filter (Pydantic introspection)**: only fields declared as `str` are eligible for embeddings.
- **Value-based filter (semantic check)**: among strings, many values (UUIDs, dates, numeric strings) carry no semantic meaning.
- **Validation helpers**: functions such as `is_uuid`, `is_date`, etc. are applied to skip these non-semantic values.

This approach ensures embeddings are generated only for text with meaningful semantic content, minimizing storage and improving search relevance.

#### Embeddable Buffer (STRING fields)

- Tracks running token count against the model’s context window
- Flushes when adding another field would exceed the token budget or batch size
- Respects `EMBEDDING_MAX_BATCH_SIZE` for local models
- Embedding text format: `path: value` (e.g. `subscription.product.name: Simple Product`)

#### Non-Embeddable Buffer

- Collects UUID, INTEGER, BOOLEAN, and DATETIME fields in parallel
- Does not use token counting (no embeddings generated)
- Always flushed together with the embeddable buffer as part of the same upsert batch

## Configuration

| Setting                         | Description                                  | Default / Source | Scope             |
| ------------------------------- | -------------------------------------------- | ---------------- | ----------------- |
| `chunk_size`                    | Number of entities processed per transaction | `1000`           | All models        |
| `EMBEDDING_SAFE_MARGIN_PERCENT` | Safety margin applied to max token budget    | `10%` / settings | All models        |
| `EMBEDDING_MAX_BATCH_SIZE`      | Maximum batch size for embedding calls       | `32` / settings  | Local models only |
| `EMBEDDING_FALLBACK_MAX_TOKENS` | Context window fallback if model unknown     | `512` / settings | Local models only |

## Strengths

- Streaming processing in chunks prevents memory exhaustion
- Incremental updates via content hashing
- Batched embedding calls optimize API usage
- Token budget prevents embedding API errors
- Path, value, value_type format of an indexed record enables very accurate searching.

## Limitations

- **Record explosion**: Deeply nested models may generate a very large number of index records
- **Path rigidity**: requires reindexing when paths change
