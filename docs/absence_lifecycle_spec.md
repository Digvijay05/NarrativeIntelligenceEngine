# Absence Lifecycle Specification
**Version:** 1.0.0 (FROZEN)

This document defines the physics of **Silence**.
In this system, absence is not "null". It is a calculated **Zero-Displacement Event**.

---

## 1. The Definition of Expectation

Absence can only exist if presence was **expected**.
The system expects continuation for any thread in `ACTIVE` state.

### 1.1 The Expectation Window
For any Thread $T$ with last update at $Tick_N$:
$$ExpectationWindow(T) = [Tick_{N+1}, Tick_{N+3}]$$

If data arrives within this window, the thread remains `ACTIVE`.
If NO data arrives by $Tick_{N+3}$, the expectation is violated.

---

## 2. State Transitions of Silence

### 2.1 Active → Dormant (The Pause)
**Trigger:** $Tick_{current} = Tick_{last} + 2$
**Action:** Flag thread as `DORMANCY`.
**Visual Semantics:** Thread line continues, but opacity reduces strictly to 50%.
**Meaning:** "Signal lost, carrier wave persists."

### 2.2 Dormant → Unresolved (The Gap)
**Trigger:** $Tick_{current} = Tick_{last} + 4$
**Action:** Create **Absence Block** starting at $Tick_{last} + 1$.
**Visual Semantics:** Thread line terminates. Hash-patterned "Void" block appears.
**Meaning:** "Expected event failed to occur."

### 2.3 Unresolved → Vanished (The Death)
**Trigger:** $Tick_{current} = Tick_{last} + 10$
**Action:** State becomes `VANISHED`.
**Visual Semantics:** Absence block fades to background. Thread ID is archived.
**Meaning:** "Narrative coherence dissolved."

---

## 3. Resurrection Rules (The Zombie Clause)

What happens if data arrives *after* a gap?

### 3.1 Dormancy Break
If data arrives during `DORMANCY`:
- State reverts to `ACTIVE`.
- No gap is recorded.
- Visual line solidifies.

### 3.2 Post-Gap Resurrection
If data arrives during `UNRESOLVED` (Tick +4 to +10):
- A new **Presence Segment** starts.
- The **Absence Block** remains fixed in history (Immutable Void).
- The thread is visually "broken" but legally the same ID.

### 3.3 The Vanished Prohibition
If data arrives after `VANISHED` (Tick > +10):
- It **CANNOT** attach to the old Thread ID.
- It MUST form a **New Thread**.
- *Rationale:* A narrative that stops for that long and restarts is structurally a restart, even if semantically identical.

---

## 4. Measurement Invariance

Absence is objective.
- It is NOT based on "importance" of the news.
- It is based purely on the **Pulse Rate** of the ingest feeds.
- If the feed polls every 5 minutes, and no item appears for 20 minutes (4 ticks), absence is proven.

**We measure the silence of the wire, not the silence of the world.**
