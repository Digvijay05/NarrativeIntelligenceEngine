# Shadow Absence Ledger (Forensic Observation)

**Phase:** Shadow Ingestion & Forensic Observation
**Constitution:** `formalization-v1.0`
**Objective:** Record behavior of Absence Invariants under real-world stress.

## Ledger Invariants
1. **Descriptive Only:** Record what happened, not how to fix it.
2. **No Intervention:** Do not restart ingestion to "fix" a feed.
3. **Raw Truth:** If the system says a thread Vanished, it Vanished.

---

## Observation Log

| Timestamp (UTC) | Source | Thread ID | Event Type | Duration | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `YYYY-MM-DD HH:MM` | `reuters_world` | `thread_...` | **Silence** | `5m` | Initial poll interval gap. |
| ... | ... | ... | ... | ... | ... |

## Anomalies & Edge Cases (Forensic Notes)

### Late Arrivals (Retroactive Injection)
*List instances where data arrived with `published_timestamp` significantly older than `ingest_timestamp`.*

### Zombie Candidates (Rejected)
*List instances where a Vanished thread received new content that forced a New Thread ID (proving the invariant).*

### Bursty Silence
*List feeds that exhibit irregular silence patterns (e.g. 2 hours silent, then 50 items).*

---

## Summary of Physics
*To be filled after 24h run.*

- Total Threads Created: `0`
- Total Dormant Transitions: `0`
- Total Vanished Transitions: `0`
- Survivor Count (Active > 24h): `0`
