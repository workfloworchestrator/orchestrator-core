# Search Indexing CLI

Typer-based CLI for maintaining search indexes (subscriptions, products, processes, workflows).

## Usage

Run from project root:

```
dotenv run python main.py index [COMMAND] [OPTIONS]
```

### Commands

- `subscriptions` – index `subscription_search_index`
- `products` – index `product_search_index`
- `processes` – index `process_search_index`
- `workflows` – index `workflow_search_index`

### Options

Each command accepts the following options:

- `--subscription-id` / `--product-id` / `--process-id` / `--workflow-id` – UUID string of a specific entity (optional, default: process all entities)
- `--dry-run` – perform indexing operations without writing to database (boolean flag)
- `--force-index` – force re-indexing even if entity hash is unchanged (boolean flag)

### Examples

```
# Index all subscriptions
dotenv run python main.py index subscriptions

# Re-index all subscriptions
dotenv run python main.py index subscriptions --force-index

# Index a single subscription
dotenv run python main.py index subscriptions --subscription-id=<UUID>
```
