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

- `--<id>` – UUID of a specific entity (default: all)
- `--dry-run` – no DB writes
- `--force-index` – re-index even if unchanged

### Examples

```
# Index all subscriptions
dotenv run python main.py index subscriptions

# Re-index all subscriptions
dotenv run python main.py index subscriptions --force-index

# Index a single subscription
dotenv run python main.py index subscriptions --subscription-id=<UUID>
```
