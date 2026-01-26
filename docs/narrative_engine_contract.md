# Narrative State Engine: Formal Contract
**Version:** 1.0.0 (FROZEN)

This document defines the **invariant laws** of the Narrative State Engine.
These are not guidelines. They are **physics**.
Any code change that violates these rules makes the system **invalid**.

---

## 1. Axioms of Assembly

### Rule 1.1: Inclusion Monotonicity
A fragment $F$ belongs to Thread $T$ if and only if:
1. **Temporal Adjacency:** $|T_{latest} - F_{timestamp}| < 24 hours$
2. **Topic Overlap:** $Jaccard(Tokens(T), Tokens(F)) > 0.3$

**Constraint:** The engine MUST NOT use "semantic similarity" (embeddings/LLMs) for inclusion unless explicitly versioned as a new layer. Simple lexical overlap is the ground truth.

### Rule 1.2: Identity Persistence
Once a fragment is assigned to Thread $T$, it **CANNOT** be moved to Thread $U$ in a future tick.
*Correction requires branching, not mutation.*

### Rule 1.3: Deterministic Replay
For any set of fragments $\{F_1, ... F_n\}$ processed in order:
The resulting state $S_n$ must be **bit-for-bit identical** regardless of:
- Wall-clock time of execution
- Hardware architecture
- Number of times replayed

---

## 2. Lifecycle Semantics

### Rule 2.1: Emergence
A new thread forms if and only if a fragment **fails** to match any existing active thread (Rule 1.1).

### Rule 2.2: Dormancy
A thread transitions from `ACTIVE` to `DORMANCY` if:
`CurrentTick - LastUpdateTick > 2`

**Meaning:** Dormancy is not "dead". It is "waiting". Data can still append to a dormant thread if it satisfies Rule 1.1.

### Rule 2.3: Unresolved State (The Gap)
A thread transitions from `DORMANCY` to `UNRESOLVED` if:
`CurrentTick - LastUpdateTick > 3`

**Meaning:** An expected continuation did not arrive. This creates an **Absence Marker** in the forensic timeline.

### Rule 2.4: Terminal State (Vanished)
A thread becomes `VANISHED` if:
`CurrentTick - LastUpdateTick > 10`
No new fragments can ever attach to a Vanished thread.

---

## 3. Forbidden Operations

The Narrative State Engine is **PROHIBITED** from:

1. **Synthesizing Text:** It shall never generate summaries, headlines, or descriptions. It only groups existing text.
2. **Predicting Outcomes:** It shall never emit probabilities of future events.
3. **Deleting History:** It shall never remove a fragment from the Event Log or State.
4. **Ranking Importance:** It shall never assign a "score" or "weight" to a thread. All threads are topologically equal.
5. **Resolving Contradictions:** If Source A says "X" and Source B says "Not X", the engine MUST preserve both as divergent branches. It must NEVER decide which is true.

---

## 4. Contradiction Logic

Contradiction is structural, not semantic.
A **Divergence Point** is generated when:
- Two fragments $F_a$ (Source A) and $F_b$ (Source B) map to the same Thread $T$.
- They occur within the same Tick.
- $Jaccard(F_a, F_b) < 0.2$ (Low internal consistency).

The engine marks this as `DIVERGENCE_DETECTED`. It does not resolve it.

---

## 5. Verification Hash

The state of the engine at Tick $N$ is valid if and only if:
$Hash(State_N) = Hash(Apply(State_{N-1}, Input_N))$
