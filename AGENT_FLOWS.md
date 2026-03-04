# Possible flows

## Flow 1: Simple Search (No Filters)

**Query**: "Search for renewable energy"

**Tool Sequence**:

```
→ run_search(entity_type=SUBSCRIPTION, limit=10)
→ Conversational response about results
```

---

## Flow 2: Filtered Search

**Query**: "Show me active subscriptions"

**Tool Sequence**:

```
→ discover_filter_paths(["status"], entity_type=SUBSCRIPTION)
→ get_valid_operators()
→ set_filter_tree(filters=FilterTree with status=active)
→ run_search(entity_type=SUBSCRIPTION, limit=10)
→ Conversational response
```

---

## Flow 3: Count Aggregation (Temporal)

**Query**: "Count subscriptions per month"

**Tool Sequence**:

```
→ discover_filter_paths(["insync_date" or "start_date"], entity_type=SUBSCRIPTION)
→ set_temporal_grouping(temporal_groups=[TemporalGrouping(field=path, period="month")])
→ run_aggregation(entity_type=SUBSCRIPTION, query_operation=COUNT, visualization_type="line_chart")
→ Brief confirmation (UI shows chart)
```

---

## Flow 4: Count with Filters

**Query**: "Count active subscriptions by status in 2025"

**Tool Sequence**:

```
→ discover_filter_paths(["status", "start_date"], entity_type=SUBSCRIPTION)
→ set_filter_tree(filters=FilterTree with status=active AND year=2025)
→ set_grouping(group_by_paths=["subscription.status"])
→ run_aggregation(entity_type=SUBSCRIPTION, query_operation=COUNT, visualization_type="bar_chart")
→ Brief confirmation
```

---

## Flow 5: Numeric Aggregation

**Query**: "What's the average price of products?"

**Tool Sequence**:

```
→ discover_filter_paths(["price"], entity_type=PRODUCT)
→ set_aggregations([FieldAggregation(type="avg", field="product.price", alias="avg_price")])
→ run_aggregation(entity_type=PRODUCT, query_operation=AGGREGATE, visualization_type="table")
→ Brief confirmation (UI shows avg_price value)
```

**Note**: AGGREGATE action for numeric operations (not counting)

---

## Flow 6: Follow-up Request (Export)

**Query 1**: "Show subscriptions"
**Query 2**: "Export these to CSV"

**Tool Sequence**:

```
Turn 1:
  → run_search(entity_type=SUBSCRIPTION, limit=10)
  → Conversational response

Turn 2:
  prepare_export()
  → Confirmation message (UI shows download link)
```

**Note**: Requires conversation history persistence (query_id from turn 1's ToolStep)

---

## Flow 7: Follow-up Request (Details)

**Query 1**: "Find subscriptions with 'fiber'"
**Query 2**: "What's the status of these?"

**Tool Sequence**:

```
Turn 1:
  → run_search(entity_type=SUBSCRIPTION, limit=10) with query_text="fiber"
  → Conversational response

Turn 2:
  fetch_entity_details(limit=10)
  → Parse detailed data and answer question about statuses
```

**Note**: Requires conversation history persistence (query_id from turn 1's ToolStep)

---

## Flow 8: General Question (No Search)

**Query**: "What entity types can I search?"

**Tool Sequence**:

```
No tools called
→ Direct text response explaining: SUBSCRIPTION, PRODUCT, WORKFLOW, PROCESS
```

---

## Flow 9: Complex Temporal + Filters + Aggregation

**Query**: "Show monthly subscription growth in 2024 by product type"

**Tool Sequence**:

```
→ discover_filter_paths(["start_date", "product"], entity_type=SUBSCRIPTION)
→ set_filter_tree(filters=FilterTree with year=2024)
→ set_temporal_grouping(temporal_groups=[TemporalGrouping(field="start_date", period="month")], cumulative=True)
→ set_grouping(group_by_paths=["product.name"])
→ run_aggregation(entity_type=SUBSCRIPTION, query_operation=COUNT, visualization_type="line_chart")
→ Brief confirmation
```

**Note**: Combines temporal grouping, regular grouping, and filters

---

## Flow 10: Count by Regular Field

**Query**: "Count subscriptions by status"

**Tool Sequence**:

```
→ discover_filter_paths(["status"], entity_type=SUBSCRIPTION)
→ set_grouping(group_by_paths=["subscription.status"])
→ run_aggregation(entity_type=SUBSCRIPTION, query_operation=COUNT, visualization_type="bar_chart")
→ Brief confirmation
```

---

## Flow 11: Multiple Aggregations

**Query**: "Show sum and average of subscription prices by status"

**Tool Sequence**:

```
→ discover_filter_paths(["status", "price"], entity_type=SUBSCRIPTION)
→ set_grouping(group_by_paths=["subscription.status"])
→ set_aggregations([
     FieldAggregation(type="sum", field="price", alias="total_price"),
     FieldAggregation(type="avg", field="price", alias="avg_price")
   ])
→ run_aggregation(entity_type=SUBSCRIPTION, query_operation=AGGREGATE, visualization_type="table")
→ Brief confirmation
```

---
