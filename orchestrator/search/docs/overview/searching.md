# Searching

This system supports multiple **search types** that can be used alone or combined:

- **Semantic** — vector similarity on embedded text (natural-language meaning).
- **Fuzzy** — trigram similarity (robust to typos and partial matches).
- **Structured** — typed filters on `path:value:type` (deterministic constraints).
- **Hybrid** — fusion of **Semantic** and **Fuzzy** using **Reciprocal Rank Fusion (RRF)**.

**Notes**

- **Score range:** final scores are normalized to `[0, 1]`; **higher is always better**.
- **Filters:** Structured filters can be applied with **any** search type (Semantic-only, Fuzzy-only, or Hybrid) to scope candidates before ranking.

## Search routing

The system automatically chooses the retriever based on user input (`parameters.py`):

- **No query, filters present** → **Structured**.
- **Query is a UUID** → **Fuzzy**.
- **Query is a single non-UUID word** → **Hybrid** (semantic **+** fuzzy).
- **Query has multiple words** → **Semantic**.

> Structured filters (if present) always scope candidates **before** ranking.

---

## Results

- A **normalized score** (0–1) for ranking.
- Optional **perfect_match** flag for very strong fuzzy matches.
- A **matching_field**: best field (path + value) with highlight spans.

---
