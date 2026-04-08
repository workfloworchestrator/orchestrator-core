# Psycopg3 Concurrency Debugging & Timeouts — Design Spec

**Datum:** 2026-03-26
**Migratie plan:** [psycopg3-migration-plan.md](../../psycopg3-migration-plan.md)
**Resterende items:** 5 (ClientCursor), 7-9 (concurrency tests), 11-12 (timeouts)

## Context

De psycopg2→psycopg3 migratie is grotendeels compleet (Fase 1 + meeste Fase 2 items). Workers hangen echter nog steeds op de "Lock subscription" stap bij concurrent gebruik. De bestaande defensieve maatregelen (pool checkin events, expliciete rollback in `database_scope`, `pool_reset_on_return`) zijn onvoldoende om het probleem op te lossen.

## Aanpak

Data-gedreven: eerst timeouts toevoegen als bescherming, dan concurrency tests schrijven die het exacte probleem reproduceren, en ten slotte ClientCursor testen als mogelijke oplossing.

## Wijzigingen

### 1. Timeouts in ENGINE_ARGUMENTS

**Bestand:** `orchestrator/db/database.py:169`

Toevoegen aan de `options` string in `connect_args`:

```python
"connect_args": {
    "connect_timeout": 10,
    "options": "-c timezone=UTC -c lock_timeout=30000 -c idle_in_transaction_session_timeout=60000",
}
```

- `lock_timeout=30000` (30s) — queries die langer dan 30s op een lock wachten krijgen een error
- `idle_in_transaction_session_timeout=60000` (60s) — PostgreSQL killt sessies die 60s idle-in-transaction zijn

Hardcoded defaults, niet configureerbaar via environment variables.

### 2. Concurrency integratietest

**Bestand:** `test/unit_tests/test_psycopg3_concurrency.py` (nieuw)

Test simuleert het productie-scenario: 3 threads proberen concurrent dezelfde `ProcessTable` rij te locken via `SELECT ... FOR UPDATE`.

**Teststrategie:**

1. Maak een `ProcessTable` rij aan
2. Start 3 threads die elk:
   - Een eigen `database_scope` openen
   - `SELECT ... FOR UPDATE` op dezelfde rij uitvoeren
   - Status updaten + committen
3. Verifieer: alle 3 threads completen binnen `lock_timeout`
4. Check `pg_stat_activity`: geen "idle in transaction" sessies na afloop

**Design decisions:**
- Threads i.p.v. asyncio — matcht het Celery worker model
- `threading.Barrier` om threads gelijktijdig te laten starten
- Timeout assertion: thread die langer dan 35s hangt → test faalt

### 3. pg_stat_activity helper

**Bestand:** zelfde testbestand

```python
def get_idle_in_transaction_count(engine) -> int:
    """Query pg_stat_activity voor idle-in-transaction sessies van deze database."""
```

Wordt gebruikt als assertion na de concurrency test om te verifiëren dat er geen connecties in "idle in transaction" state achterblijven.

### 4. ClientCursor vergelijkingstest

**Bestand:** zelfde testbestand

Test wordt geparametriseerd met `@pytest.mark.parametrize("use_client_cursor", [False, True])`:

- `server-side`: standaard psycopg3 gedrag (server-side binding)
- `client-side`: met `psycopg.ClientCursor` (client-side binding, zoals psycopg2)

Zo wordt in de testoutput direct zichtbaar of de binding-strategie verschil maakt:

```
test_concurrent_for_update[server-side]   PASSED/FAILED
test_concurrent_for_update[client-side]   PASSED/FAILED
```

De ClientCursor engine wordt aangemaakt via een fixture die een aparte engine + session configureert met `cursor_factory=ClientCursor` in `connect_args`.

## Scope

| Component | Bestand | Type wijziging |
|-----------|---------|----------------|
| Timeouts | `orchestrator/db/database.py` | Edit bestaand |
| Concurrency test | `test/unit_tests/test_psycopg3_concurrency.py` | Nieuw bestand |
| pg_stat_activity helper | Zelfde testbestand | Nieuw |
| ClientCursor vergelijking | Zelfde testbestand | Nieuw |

**Geen wijzigingen aan:** workflow logica, session management, pool configuratie (anders dan timeouts), dependencies.