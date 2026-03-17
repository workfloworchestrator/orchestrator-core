# Psycopg2 naar Psycopg3 Migratie — Analyse & Plan

**Datum:** 2026-03-17
**PR:** [#1093](https://github.com/workfloworchestrator/orchestrator-core/pull/1093)
**Issue:** [#1097](https://github.com/workfloworchestrator/orchestrator-core/issues/1097)

## Het probleem

Bij de SURF Orchestrator met 3 Celery workers en meerdere gelijktijdige validatie-taken hangen alle workers op de "Lock subscription" stap. Deze stap doet alleen een `UPDATE` op de `subscription` tabel, maar PostgreSQL toont geblokkeerde queries op de `process_steps` tabel.

## Meest waarschijnlijke oorzaken

### 1. "Idle in Transaction" door impliciete transacties (HOOG RISICO)

psycopg3 heeft hetzelfde `autocommit=False` gedrag als psycopg2, maar het interageert anders met SQLAlchemy's "autobegin". Er ontstaat een dubbele laag:

- SQLAlchemy start impliciet een transactie bij eerste gebruik
- psycopg3 start **ook** impliciet een transactie

Als de workflow engine een stap uitvoert via `transactional()` (`orchestrator/db/database.py:234-271`), en de commit of rollback niet correct doorpropageert naar de psycopg3-laag, blijft de connectie "idle in transaction" en worden locks niet vrijgegeven.

**Achtergrond:** Met psycopg2 was er ook een implicit `BEGIN`, maar SQLAlchemy's session management was hier volledig op afgestemd. psycopg3 gebruikt een subtiel ander transactie-lifecyclemodel:

- `conn.transaction()` op een bestaande impliciete transactie creëert een **savepoint** i.p.v. een nieuwe transactie
- De buitenste impliciete transactie blijft open
- Ontwikkelaars die verwachten dat `transaction()` de volledige transactie beheert, kunnen onbedoeld transacties langer open laten

### 2. Server-Side Parameter Binding (HOOG RISICO)

psycopg3 gebruikt standaard **server-side binding** (`$1, $2` placeholders) i.p.v. psycopg2's client-side binding. Dit kan:

- Bepaalde raw SQL statements (`text()`) laten falen, waardoor transacties half-open blijven
- Query plans veranderen, wat lock-acquisitie patronen beïnvloedt
- De `REFRESH MATERIALIZED VIEW CONCURRENTLY` in `settings.py:84` kan zich anders gedragen
- DDL/utility statements die geen geparametriseerde queries accepteren (`SET`, `NOTIFY`, `CREATE DATABASE`) falen met syntax errors

### 3. `with_for_update()` + transactiescoping conflict (HOOG RISICO)

De codebase gebruikt `with_for_update()` op meerdere plekken:

| Locatie | Doel |
|---------|------|
| `orchestrator/services/executors/threadpool.py:54` | Lockt ProcessTable rij voordat status naar RUNNING gaat |
| `orchestrator/services/executors/celery.py:108` | Zelfde patroon voor Celery executor |
| `orchestrator/services/settings.py:36` | Lockt EngineSettings bij update |
| `orchestrator/services/subscriptions.py:89` | Optionele lock op subscriptions |

Als een worker een `SELECT ... FOR UPDATE` uitvoert op een `ProcessTable` rij, en de transactie niet correct wordt afgesloten (door het psycopg3 transactie-verschil), blijven **alle andere workers** die dezelfde rij willen locken hangen.

### 4. De `transactional()` finally-rollback interactie

```python
# orchestrator/db/database.py:234-271
@contextmanager
def transactional(db, log):
    try:
        with disable_commit(db, log):
            yield
        db.session.commit()
    except Exception:
        raise
    finally:
        db.session.rollback()  # ← altijd rollback als safety net
```

Met psycopg3 kan de `rollback()` in `finally` een **andere** transactie-state tegenkomen dan verwacht, vooral als de `commit()` eerder een savepoint creëerde in plaats van een echte commit.

### 5. psycopg2-specifieke error import (BLOKKEREND)

`orchestrator/metrics/dbutils.py:5` importeert `from psycopg2 import errors` — dit crasht direct met psycopg3.

## Belangrijke gedragsverschillen psycopg2 vs psycopg3

| Aspect | psycopg2 | psycopg3 | Locking risico |
|--------|----------|----------|----------------|
| Default autocommit | `False` | `False` | Gelijk |
| `with conn:` sluit | Alleen transactie | **Connectie** | Ander resource lifecycle |
| Parameter binding | Client-side | **Server-side** | DDL failures kunnen locks achterlaten |
| `conn.transaction()` op bestaande txn | N/A | **Creëert savepoint** | Buitenste txn blijft open |
| Transactie params in autocommit | Worden toegepast | **Genegeerd** | Stille gedragswijziging |
| Meerdere statements in execute() | Werkt (laatste resultaat) | **Errors** | Partiële executie risico |
| `idle_in_transaction` risico | Aanwezig | **Versterkt** door savepoint verwarring | Hoger |

## Relevante codebase-patronen

### Engine & Session configuratie (`orchestrator/db/database.py`)

```python
ENGINE_ARGUMENTS = {
    "connect_args": {"connect_timeout": 10, "options": "-c timezone=UTC"},
    "pool_pre_ping": True,
    "pool_size": 60,
    "json_serializer": json_dumps,
    "json_deserializer": json_loads,
}
SESSION_ARGUMENTS = {
    "class_": WrappedSession,
    "autocommit": False,
    "autoflush": True,
    "query_cls": SearchQuery,
}
```

- Pool type: default QueuePool (60 connections)
- Custom `WrappedSession` die commit blokkeert tijdens workflow steps
- ContextVar-based scope management voor async compatibiliteit

### Workflow executie flow

1. Worker pikt taak op
2. `database_scope()` creëert nieuwe session scope
3. `with_for_update()` lockt ProcessTable rij
4. `transactional()` wrapt elke workflow step
5. `commit()` of `rollback()` aan einde van step
6. Finale `commit()` aan einde van proces

## Migratieplan

### Fase 1: Directe fixes (vereist)

| # | Actie | Bestand | Risico |
|---|-------|---------|--------|
| 1 | Dependency swap: `psycopg2-binary` → `psycopg[binary]>=3.2` | `pyproject.toml` | Laag |
| 2 | URI schema: `postgresql://` → `postgresql+psycopg://` | settings, CI, docs | Laag |
| 3 | Fix `psycopg2.errors` import → `psycopg.errors` | `metrics/dbutils.py` | Laag |

### Fase 2: Transactie-gedrag onderzoeken & fixen

| # | Actie | Details |
|---|-------|---------|
| 4 | **Test `pool_reset_on_return`** | Verifieer dat SQLAlchemy's pool correct `ROLLBACK` + `DISCARD ALL` stuurt bij psycopg3 connectie-return |
| 5 | **Overweeg `server_side_binding=False`** | Voeg `connect_args={"cursor_factory": psycopg.ClientCursor}` toe aan `ENGINE_ARGUMENTS` om client-side binding te forceren (elimineert binding-gerelateerde issues) |
| 6 | **Audit `transactional()` CM** | Test of `commit()` + `finally: rollback()` patroon correct werkt met psycopg3's transactie-state |
| 7 | **Test concurrent `with_for_update()`** | Reproduceer het exacte scenario: 3 workers, meerdere validatie-taken, monitor `pg_stat_activity` voor "idle in transaction" |

### Fase 3: Reproduceerbaarheid & validatie

| # | Actie |
|---|-------|
| 8 | Schrijf een integratietest die 3+ concurrent workflow-processen start met `with_for_update()` |
| 9 | Monitor `pg_stat_activity` tijdens tests: `SELECT pid, state, query, wait_event_type, wait_event FROM pg_stat_activity WHERE state != 'idle'` |
| 10 | Vergelijk lock-gedrag psycopg2 vs psycopg3 met dezelfde test |

### Fase 4: Optionele verbeteringen

| # | Actie | Details |
|---|-------|---------|
| 11 | Voeg `lock_timeout` toe aan `connect_args` | Voorkom eindeloos wachten op locks: `options: "-c lock_timeout=30000"` (30s) |
| 12 | Overweeg `idle_in_transaction_session_timeout` | Server-side safety net: kill sessies die te lang idle-in-transaction zijn |

## Aanbevolen eerste stap

De snelste manier om te verifiëren of server-side binding het probleem is: voeg `cursor_factory: psycopg.ClientCursor` toe aan de `connect_args` in `orchestrator/db/database.py` en test opnieuw. Dit schakelt het grootste gedragsverschil tussen psycopg2 en psycopg3 uit.

Als dat het probleem niet oplost, focus dan op de `transactional()` context manager en de interactie met psycopg3's impliciete transacties — dit is het meest waarschijnlijke pad naar het "idle in transaction" probleem.

## Bronnen

- [Differences from psycopg2 — psycopg3 docs](https://www.psycopg.org/psycopg3/docs/basic/from_pg2.html)
- [Transactions management — psycopg3 docs](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)
- [Connection pools — psycopg3 docs](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
- [Using psycopg over psycopg2 — SQLAlchemy Discussion #11648](https://github.com/sqlalchemy/sqlalchemy/discussions/11648)
- [SQLAlchemy PostgreSQL dialect docs](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html)
- [Avoiding idle-in-transaction — Gorgias Engineering](https://www.gorgias.com/blog/prevent-idle-in-transaction-engineering)