# Parallel Step Stress Integration Tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stress-test parallel and foreach_parallel with complex compositions (nesting, mixing, asymmetric branches) via integration tests that exercise the full DB path.

**Architecture:** Single test file using the engine-pool `db_session` fixture pattern from `test_parallel_workflow.py`. Each test registers a workflow, runs it via `runwf`, and verifies both the workflow result and DB persistence (fork steps, relations, branch steps).

**Tech Stack:** pytest, SQLAlchemy, orchestrator workflow DSL

---

## File Structure

- **Create:** `test/unit_tests/test_parallel_stress.py` — all stress/integration tests
- **Read only:** `orchestrator/workflow.py` — parallel execution engine (only modify if true bug found)
- **Read only:** `test/unit_tests/test_parallel_workflow.py` — fixture patterns to reuse

---

### Task 1: Scaffold test file with fixtures and helpers

**Files:**
- Create: `test/unit_tests/test_parallel_stress.py`

- [ ] **Step 1: Create test file with imports, db_session fixture, and helper functions**

```python
# Reuse the engine-pool db_session fixture pattern from test_parallel_workflow.py
# Add helpers: register_test_workflow, create_new_process_stat, store, _get_fork_steps, _get_relations
```

- [ ] **Step 2: Run empty test file to verify imports**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py --collect-only`
Expected: 0 tests collected, no import errors

- [ ] **Step 3: Commit**

```bash
git add test/unit_tests/test_parallel_stress.py
git commit -m "Add scaffold for parallel stress integration tests"
```

---

### Task 2: Nested parallel tests

**Files:**
- Modify: `test/unit_tests/test_parallel_stress.py`

Test scenarios:
- Parallel block where one branch itself contains a parallel block (2 levels deep)
- Three levels of nesting
- Verify DB creates fork steps at each nesting level with correct branch counts
- Verify all branch steps are linked via ProcessStepRelationTable

- [ ] **Step 1: Write test for 2-level nested parallel**
- [ ] **Step 2: Write test for 3-level nested parallel**
- [ ] **Step 3: Run tests**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py -k nested -v`

- [ ] **Step 4: Commit**

---

### Task 3: Mixed parallel and foreach_parallel tests

**Files:**
- Modify: `test/unit_tests/test_parallel_stress.py`

Test scenarios:
- `parallel` containing a branch with `foreach_parallel`
- `foreach_parallel` where each item's branch contains a `parallel` block
- Sequential chain: `parallel >> foreach_parallel >> parallel`
- `foreach_parallel` nested inside `foreach_parallel`

- [ ] **Step 1: Write test for parallel with foreach_parallel branch**
- [ ] **Step 2: Write test for foreach_parallel with parallel inside each branch**
- [ ] **Step 3: Write test for sequential chain of parallel blocks**
- [ ] **Step 4: Write test for nested foreach_parallel**
- [ ] **Step 5: Run tests**
- [ ] **Step 6: Commit**

---

### Task 4: Asymmetric branch tests

**Files:**
- Modify: `test/unit_tests/test_parallel_stress.py`

Test scenarios:
- Branches with vastly different step counts (1 step vs 5 steps)
- One branch does real work, another is a no-op (returns empty dict)
- foreach_parallel over items of different "weight" (some items produce many steps)
- Verify DB relations have correct order_ids for each branch regardless of length

- [ ] **Step 1: Write parametrized test for asymmetric branch lengths**
- [ ] **Step 2: Write test verifying DB relation order_ids for asymmetric branches**
- [ ] **Step 3: Run tests**
- [ ] **Step 4: Commit**

---

### Task 5: Scale / concurrency stress tests

**Files:**
- Modify: `test/unit_tests/test_parallel_stress.py`

Test scenarios:
- `parallel` with 10 branches (stress thread pool + DB writes)
- `foreach_parallel` over 20 items (many concurrent branches)
- `max_workers` throttling: 20 items with max_workers=3
- Verify all fork steps and relations are correctly persisted under concurrency

- [ ] **Step 1: Write test for 10-branch parallel with DB verification**
- [ ] **Step 2: Write test for 20-item foreach_parallel**
- [ ] **Step 3: Write test for max_workers throttling**
- [ ] **Step 4: Run tests**
- [ ] **Step 5: Commit**

---

### Task 6: Error propagation in complex compositions

**Files:**
- Modify: `test/unit_tests/test_parallel_stress.py`

Test scenarios:
- Error in inner nested parallel propagates to outer parallel (fails the whole thing)
- Error in one foreach_parallel branch while nested inside a parallel
- Retryable step inside nested parallel returns Waiting
- Mixed: one nested group fails, another succeeds — outer fails
- Verify partial DB state is consistent (fork steps, relations for completed branches)

- [ ] **Step 1: Write test for error in nested parallel**
- [ ] **Step 2: Write test for retryable step in nested parallel**
- [ ] **Step 3: Write test for mixed success/failure in nested groups**
- [ ] **Step 4: Run tests**
- [ ] **Step 5: Commit**

---

### Task 7: Edge cases

**Files:**
- Modify: `test/unit_tests/test_parallel_stress.py`

Test scenarios:
- foreach_parallel with single item (should work like a single branch)
- foreach_parallel where items are produced by a previous foreach_parallel (state doesn't merge — this should handle gracefully)
- Parallel block immediately after another parallel block (back-to-back)
- Large state object passed through parallel (verify deep copy doesn't corrupt)
- Conditional step inside a branch of a nested parallel

- [ ] **Step 1: Write edge case tests**
- [ ] **Step 2: Run all tests**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py -v`

- [ ] **Step 3: Commit**

---

### Task 8: Final verification

- [ ] **Step 1: Run full test suite to ensure no regressions**

Run: `uv run pytest test/unit_tests/test_parallel_stress.py test/unit_tests/test_parallel_workflow.py test/unit_tests/test_parallel_db.py -v`

- [ ] **Step 2: Run type checker**

Run: `uv run mypy test/unit_tests/test_parallel_stress.py`

- [ ] **Step 3: Run linter**

Run: `uv run ruff check test/unit_tests/test_parallel_stress.py`

- [ ] **Step 4: Final commit with all passing**
