# Search benchmark

Measures whether a change to the text search (the fuzzy retriever) makes results better or worse. Semantic and hybrid
retrieval are out of scope: they depend on the embedding model and its size.

Accuracy is scored against *labels*, not against recorded output of the engine, so a wrong result is not locked in as
correct. A *label* is the answer key of a query: the entities it should find (`expected`).

## How it works

1. `corpus.py` + `profiles/generic.py`: a seeded corpus of network services (service ports, light paths, L2VPNs, IP
   peerings) shaped like orchestrator subscriptions: product blocks nested up to six deep, block ids, inventory ids and
   flags next to the names, code-style descriptions, confusable sites, neighbouring node names and customers on
   several services. The same seed and size give the same corpus; nothing large is committed.
2. The corpus is indexed through the real `Indexer` into `ai_search_index`, in a database built by the real Alembic
   migrations (the integration test fixtures).
3. Queries: ~40 hand-written ones (`queries/handwritten.yaml`, each with a note on the intended behaviour) plus
   generated ones (`perturb.py`: exact, prefix, customer typo, reorder, case/punctuation, identifier, customer plus
   location). They run through `execute_search` with `retriever=fuzzy`.
4. Metrics per category (`metrics.py`): MRR, Success@1, Recall@10, and the false-positive rate of `negative` queries.
   Recall@10 is the share of what fits in 10 results, so a query that matches hundreds of entities can reach 1.0.
5. The plan of every query is checked to use the trigram index and never to scan `ai_search_index` sequentially. What
   the fuzzy statement costs Postgres is measured by `test/integration_tests/search/performance`, not here.

### What gets indexed

Every entity is a subscription-like `NetworkService` (`profiles/generic.py`): the root fields of a `SubscriptionModel`,
its `product`, and one product block. A service port has a `port`; a light path a `vc` with two service attach points
(`saps`); an L2VPN a `vc` with two to four `esis`, each with a sap; an IP peering an `ip_peering` with `peers`, each
with a sap. Every sap holds a `port` on a `node`. Every block carries the ids orchestrator-core's `ProductBlockModel`
gives it (`subscription_instance_id`, `owner_subscription_id`), so most indexed values are UUIDs, numbers and flags,
as in production: about 56 fields per entity, 170,000 rows for the benchmark corpus.

The description is `customer abbreviation, product tag, sites, speed`, as orchestrators build it. It names every site,
sorted; a multipoint L2VPN its first three. A service's first end is its A-end, the others its B-ends. An anchor, as
indexed (block ids shortened):

```json
{
  "subscription_id": "0fc80d4c-85f1-52fc-9efe-f8792ddeda04",
  "description": "NWR LP AMS001A-RTD001A 10 Gbit/s",
  "status": "active",
  "insync": true,
  "start_date": "2023-08-15T00:00:00",
  "version": 1,
  "customer_id": "e1f78731-95cf-57d4-a821-ccfb32b8ac25",
  "customer_name": "Northwind Research",
  "customer_abbreviation": "NWR",
  "product": {"product_id": "546471af-…", "name": "Light Path", "description": "Light Path",
              "product_type": "LightPath", "tag": "LP", "status": "active"},
  "vc": {
    "name": "Light Path Virtual Circuit", "subscription_instance_id": "023658e3-…", "owner_subscription_id": "0fc80d4c-…",
    "service_speed": 10000, "speed_policer": false, "remote_port_shutdown": true, "inventory_id": 868656,
    "saps": [
      {"name": "Service Attach Point", "subscription_instance_id": "a980f617-…", "owner_subscription_id": "0fc80d4c-…",
       "vlanrange": "210",
       "port": {"name": "Service Port", "subscription_instance_id": "cb20b884-…", "owner_subscription_id": "85f20d45-…",
                "port_name": "xe-1/2/4", "port_speed": 10000, "port_mode": "tagged", "admin_state": "enabled",
                "lldp": false, "inventory_id": 199024,
                "node": {"name": "Node", "subscription_instance_id": "4371291e-…", "owner_subscription_id": "f24d3a57-…",
                         "node_name": "ams001a-rt07", "site_code": "AMS001A", "city": "Amsterdam",
                         "node_role": "access", "inventory_id": 362306}}},
      {"…": "the B-end, on rtd001a-rt07 xe-1/2/4 in RTD001A, Rotterdam"}
    ]
  }
}
```

To see the whole corpus, with each entity's facts, run `show_corpus` (see [Run](#run)).

## Anchors

A hand-written query lists its correct answers by hand, so that list is only right if no generated entity is also a
correct answer. If the generator made a "Bluefin Hospital" in Amsterdam, it would be a correct answer to
`bluefin amsterdam` that the YAML does not list: returning it would count as wrong and push the listed answer down.

Anchors avoid that: a few hand-designed entities (`anchors()` in the profile) that are always in the corpus, whatever
the seed. Hand-written queries refer to them by key (`expected: [ams001a-rt10]`), and the generator never produces an
entity that competes with them: generated entities never reuse an anchor's node names or (customer family, location)
pairs (`reserved_nodes()`, `reserved_pairs()`). Anchors are near-misses of each other (`ams001a-rt01` against
`ams001a-rt10`, Amsterdam against Amstelveen), so each query tests one specific distinction. The list is at the top of
`queries/handwritten.yaml`.

## Query categories

| category           | the query is...                                                  | example                            |
| ------------------ | ---------------------------------------------------------------- | ---------------------------------- |
| `exact`            | an entity's full description, unchanged                          | `NWR LP AMS001A-RTD001A 10 Gbit/s` |
| `prefix`           | the description cut off at 60-80%                                | `NWR LP AMS001A-RTD0`              |
| `typo`             | one field mistyped, hand-written only                            | `ams001a-tr01`                     |
| `customer_typo`    | the customer's name with two neighbouring letters swapped        | `Nrothwind Research`               |
| `reorder`          | the description's words shuffled                                 | `AMS001A-RTD001A NWR 10 LP Gbit/s` |
| `case_punctuation` | a node name in upper case, or without `-`                        | `AMS001A RT07`                     |
| `identifier`       | a node name, IP prefix, ASN or (partial) UUID                    | `ams001a-rt07`                     |
| `multi_field`      | a customer plus a city, from different blocks of the entity      | `Bluefin University Amsterdam`     |
| `negative`         | text that should find nothing (hand-written only)                | `zxqv blorp`                       |

A `customer_typo` query expects every service of the customer, so for it Recall@10 is the share of the top 10 that is
that customer's.

### Generated queries

`perturb.py` makes queries from the corpus itself, so their labels need no hand-writing:

1. Sample 20 entities with the seed; every category uses the same 20.
2. Per category, join the first value of each fact that category uses (`GENERATORS`) and apply its perturbation, as in
   the table above. Queries shorter than 5 characters are dropped.
3. The label is every entity holding the same facts among any of its values (a B-end too), not only the entity the
   query came from.

Labels compare the unperturbed facts, except for `prefix`: a cut-off description is answered by every entity whose
description starts with it, as `NWL IP GRQ002A 1` is the start of a 1 and a 100 Gbit/s service alike. All categories
draw from one random sequence, so changing `GENERATORS` changes the queries of the categories after it.

## Reading the results

`baseline/accuracy.md` is the committed table, one row per category. All scores run from 0 to 1, averaged over the
queries of a category.

- **MRR (Mean Reciprocal Rank)**: how high the first right answer ranks. 1 at rank 1, 0.5 at rank 2, 0.33 at rank 3, 0
   when not found.
- **Success@1**: the share of queries with a right answer on top. Rank 2 counts as a miss.
- **Recall@10**: the share of right answers in the top 10, capped at 10. Is it found at all?
- **false positives**: the share of `negative` queries that returned anything. Lower is better.

High Recall@10 with low Success@1 means search finds the answer but ranks it too low. To see *why* a metric moved,
read `report/rankings.md` (not committed): the top 10 of every query with the indexed value that matched. Keep the
page of the run before a change to diff against.

## Reproducibility

The seed and corpus size are fixed. `pg_trgm.word_similarity_threshold` is pinned in `runner.py`; orchestrator-core
does not set it, so production uses the server default, and the benchmark pins that default so it cannot change
unseen. Downstream users who change it should change it there too. The accuracy table has been the same on Postgres 15
and 17, so there is one baseline, not one per version.

## Run

```bash
uv run pytest test/benchmarks/search            # accuracy against the baseline, needs Docker for Postgres
uv run pytest test/unit_tests/benchmarks        # the pure parts: corpus, perturbations, metrics, query loader
```

To see the corpus the benchmark indexes, as JSON with each entity's facts and model (the default seed is the
benchmark's):

```bash
uv run python -m test.benchmarks.search.show_corpus --size 20 --output corpus.json
```

The orchestrator logs to stdout on import, so use `--output` for a file with JSON only.

## Update the baseline

```bash
uv run pytest test/benchmarks/search --inline-snapshot=fix
git diff test/benchmarks/search/baseline
```

Review the diff per category before committing: an improvement for typos that hurts identifier lookup shows here and
disappears in an average. When the baseline file does not exist yet, use `--inline-snapshot=create` instead.
