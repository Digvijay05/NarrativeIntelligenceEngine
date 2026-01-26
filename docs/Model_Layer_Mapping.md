# ML Library → Backend Layer Mapping

## Forensic Architecture Alignment

This document maps selected ML libraries to the 6-layer backend architecture, with explicit **fence posts** marking where machine learning must stop.

> [!CAUTION]
> **Constitutional Boundary**: ML computes geometry and surfaces uncertainty. It NEVER decides, infers, ranks, or predicts. All ML outputs cross layer boundaries as **immutable contracts** only.

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ML FENCE POST LEGEND                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  🚫 = ML FORBIDDEN (inference would violate forensic integrity)            │
│  ⚙️  = ML COMPUTES (coordinate transforms, geometry, alignment)             │
│  📊 = UNCERTAINTY SURFACED (distributions, not point estimates)             │
│  📤 = OUTPUT CONTRACT (immutable, crosses to next layer)                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer-by-Layer ML Mapping

### Layer 1: Ingestion

**Purpose**: Raw data capture from external sources  
**ML Allowed**: ❌ NONE

| What Happens | ML Role | Fence Post |
|--------------|---------|------------|
| HTTP fetch | None | 🚫 No preprocessing |
| Raw bytes storage | None | 🚫 No filtering |
| Provenance tagging | None | 🚫 No quality scoring |

**Constitutional Rule**: Ingestion is a **tape recorder**. It captures exactly what arrives, when. No ML touches this layer.

**Output Contract**: `RawIngestionEvent` (verbatim payload, hash, timestamp, tier)

---

### Layer 2: Normalization

**Purpose**: Transform raw events into canonical fragments  
**ML Allowed**: ⚙️ Coordinate transforms only

#### Library Mapping

| Library | Function | What It Computes | Fence Post |
|---------|----------|------------------|------------|
| **sentence-transformers** | Embedding generation | Vector coordinates in semantic space | 🚫 No similarity thresholds that imply "same meaning" |
| **gensim** (TF-IDF) | Term weighting | Frequency-based coordinates | 🚫 No topic classification |

#### Detailed Constraints

```python
# ✅ ALLOWED: Compute embedding as coordinate transform
embedding = model.encode(text)  # Just a vector

# 🚫 FORBIDDEN: Threshold that implies semantic equivalence
if cosine_sim(a, b) > 0.8:  # Who decided 0.8 means "same"?
    return "duplicate"      # FORBIDDEN - this is inference
    
# ✅ ALLOWED: Return raw similarity as data
return {
    "similarity_score": cosine_sim(a, b),  # Surface the number
    "threshold_applied": None              # No decision made
}
```

#### ML Stops Here

| Computation | Status |
|-------------|--------|
| Vector embedding | ⚙️ Allowed |
| Cosine distance | ⚙️ Allowed |
| Duplicate decision | 🚫 FORBIDDEN |
| Topic classification | 🚫 FORBIDDEN |
| Entity resolution | 🚫 FORBIDDEN |

**Output Contract**: `NormalizedFragment` (with `DuplicateInfo.status = UNDETERMINED` if ML can't decide without inference)

---

### Layer 3: Core Narrative State Engine

**Purpose**: Thread construction, lifecycle, divergence detection  
**ML Allowed**: ⚙️ Geometry and alignment only

#### Library Mapping

| Library | Function | What It Computes | Fence Post |
|---------|----------|------------------|------------|
| **NetworkX** | Graph construction | Topology (nodes, edges) | 🚫 No centrality rankings |
| **tslearn** (DTW) | Timeline alignment | Temporal distance between sequences | 🚫 No "earlier is more authoritative" |
| **hdbscan** | Fragment grouping | Cluster membership + noise | 🚫 No "best cluster" selection |
| **hmmlearn** | State labeling | Transition probabilities | 🚫 No prediction of next state |

#### Detailed Constraints

##### NetworkX (Graph Topology)

```python
# ✅ ALLOWED: Build co-occurrence graph
G = nx.Graph()
G.add_edge(fragment_a, fragment_b, weight=overlap_score)

# ✅ ALLOWED: Detect connected components (structural)
components = list(nx.connected_components(G))

# 🚫 FORBIDDEN: PageRank or centrality (implies importance)
important = nx.pagerank(G)  # FORBIDDEN

# 🚫 FORBIDDEN: Shortest path as "narrative flow"
path = nx.shortest_path(G, a, b)  # Only if not interpreted as causality
```

##### tslearn (Dynamic Time Warping)

```python
# ✅ ALLOWED: Compute alignment distance
distance = dtw(timeline_a, timeline_b)

# ✅ ALLOWED: Return alignment path (which points matched)
path = dtw_path(timeline_a, timeline_b)

# 🚫 FORBIDDEN: "Timeline A is more complete"
completeness = score_completeness(timeline_a)  # FORBIDDEN

# 🚫 FORBIDDEN: "Source X reported first" as authority
authority = first_reporter_bonus(timeline_a)  # FORBIDDEN
```

##### hdbscan (Clustering)

```python
# ✅ ALLOWED: Cluster with explicit noise
clusterer = hdbscan.HDBSCAN(min_cluster_size=3)
labels = clusterer.fit_predict(embeddings)

# ✅ REQUIRED: Preserve noise label (-1) as UNASSIGNED
unassigned = [i for i, l in enumerate(labels) if l == -1]

# 🚫 FORBIDDEN: Force all fragments into clusters
# 🚫 FORBIDDEN: "Cluster 0 is the main narrative"
# 🚫 FORBIDDEN: Merge noise into nearest cluster
```

##### hmmlearn (State Machines)

```python
# ✅ ALLOWED: Label current lifecycle state
state_probs = model.predict_proba(observations)

# ✅ REQUIRED: Surface distribution, not argmax
return {
    "EMERGING": state_probs[0],
    "ACTIVE": state_probs[1],
    "DORMANT": state_probs[2]
}  # Let frontend show uncertainty

# 🚫 FORBIDDEN: Predict next state
# 🚫 FORBIDDEN: "Thread will terminate in 3 days"
```

#### ML Stops Here

| Computation | Status |
|-------------|--------|
| Graph construction | ⚙️ Allowed |
| DTW alignment | ⚙️ Allowed |
| Cluster membership | ⚙️ Allowed |
| State probability | 📊 Uncertainty surfaced |
| Importance ranking | 🚫 FORBIDDEN |
| Prediction | 🚫 FORBIDDEN |
| Causality | 🚫 FORBIDDEN |

**Output Contract**: `ThreadStateSnapshot` (with `divergence_reason` as observation, not judgment)

---

### Layer 4: Temporal Storage

**Purpose**: Append-only versioned persistence  
**ML Allowed**: ❌ NONE

| What Happens | ML Role | Fence Post |
|--------------|---------|------------|
| Version creation | None | 🚫 No compression via summarization |
| Timeline indexing | None | 🚫 No importance-based pruning |
| Snapshot storage | None | 🚫 No "stale" detection |

**Constitutional Rule**: Storage is a **geological record**. Every version is preserved exactly as emitted. No ML touches this layer.

**Output Contract**: `VersionedSnapshot`, `Timeline`

---

### Layer 5: Query

**Purpose**: Read-only access to stored data  
**ML Allowed**: ⚙️ Search and retrieval geometry only

#### Library Mapping

| Library | Function | What It Computes | Fence Post |
|---------|----------|------------------|------------|
| **sentence-transformers** | Query embedding | Vector for similarity search | 🚫 No "most relevant" ranking |
| **PyTorch** | Distance computation | Vectorized distance metrics | 🚫 No learned ranking |

#### Detailed Constraints

```python
# ✅ ALLOWED: Embed query, return K nearest
query_vec = model.encode(query)
results = index.search(query_vec, k=100)

# ✅ REQUIRED: Return all K with distances (no filtering)
return [
    {"fragment_id": id, "distance": d}
    for id, d in zip(results.ids, results.distances)
]

# 🚫 FORBIDDEN: Filter by learned threshold
# 🚫 FORBIDDEN: Re-rank by "relevance"
# 🚫 FORBIDDEN: Collapse near-duplicates in results
```

#### ML Stops Here

| Computation | Status |
|-------------|--------|
| Query embedding | ⚙️ Allowed |
| Distance-based retrieval | ⚙️ Allowed |
| K-nearest neighbors | ⚙️ Allowed (unfiltered) |
| Relevance ranking | 🚫 FORBIDDEN |
| Result summarization | 🚫 FORBIDDEN |

**Output Contract**: `QueryResult` (with raw distances, not relevance scores)

---

### Layer 6: Observability

**Purpose**: Logging, metrics, replay, lineage  
**ML Allowed**: 📊 Anomaly detection (uncertainty surfaced only)

#### Library Mapping

| Library | Function | What It Computes | Fence Post |
|---------|----------|------------------|------------|
| **PyMC** | Distribution modeling | Posterior distributions | 🚫 No point estimates |
| **ArviZ** | Trace inspection | Diagnostic visualizations | 📊 Surface uncertainty |

#### Detailed Constraints

```python
# ✅ ALLOWED: Compute distribution over normal behavior
with pm.Model():
    rate = pm.Exponential("ingestion_rate", lam=1/expected_rate)
    obs = pm.Poisson("observed", mu=rate, observed=data)
    trace = pm.sample()

# ✅ REQUIRED: Report full posterior, not point estimate
return {
    "ingestion_rate": {
        "mean": trace["ingestion_rate"].mean(),
        "std": trace["ingestion_rate"].std(),
        "hdi_3%": az.hdi(trace, hdi_prob=0.94)["ingestion_rate"][0],
        "hdi_97%": az.hdi(trace, hdi_prob=0.94)["ingestion_rate"][1]
    }
}

# 🚫 FORBIDDEN: "Ingestion rate is 5.2" (point estimate hides uncertainty)
# 🚫 FORBIDDEN: "Anomaly detected" (binary decision from continuous distribution)
```

#### ML Stops Here

| Computation | Status |
|-------------|--------|
| Distribution fitting | 📊 Allowed (surfaces uncertainty) |
| Credible intervals | 📊 Allowed |
| Trace diagnostics | 📊 Allowed |
| Anomaly classification | 🚫 FORBIDDEN |
| Automated alerting | 🚫 FORBIDDEN |

**Output Contract**: `MetricPoint` (with uncertainty bounds, not binary flags)

---

## Complete Library → Layer Matrix

| Library | L1 Ingestion | L2 Normalization | L3 Core Engine | L4 Storage | L5 Query | L6 Observability |
|---------|:------------:|:----------------:|:--------------:|:----------:|:--------:|:----------------:|
| **PyTorch** | ❌ | ⚙️ tensor ops | ⚙️ distance | ❌ | ⚙️ search | ❌ |
| **sentence-transformers** | ❌ | ⚙️ embeddings | ❌ | ❌ | ⚙️ query embed | ❌ |
| **gensim** | ❌ | ⚙️ TF-IDF | ❌ | ❌ | ❌ | ❌ |
| **NetworkX** | ❌ | ❌ | ⚙️ topology | ❌ | ❌ | ❌ |
| **tslearn** | ❌ | ❌ | ⚙️ DTW | ❌ | ❌ | ❌ |
| **hdbscan** | ❌ | ❌ | ⚙️ clustering | ❌ | ❌ | ❌ |
| **hmmlearn** | ❌ | ❌ | ⚙️ states | ❌ | ❌ | ❌ |
| **PyMC** | ❌ | ❌ | ❌ | ❌ | ❌ | 📊 distributions |
| **ArviZ** | ❌ | ❌ | ❌ | ❌ | ❌ | 📊 diagnostics |

---

## Known Unknowns (Tracked)

| ID | Unknown | Layer | Mitigation |
|----|---------|-------|------------|
| K1 | Embedding stability under adversarial paraphrasing | L2 | Track embedding drift per source |
| K2 | DTW scaling with high-frequency ingestion | L3 | SAX compression via pyts |
| K3 | Human tolerance for UNASSIGNED fragments | L3/Frontend | UX study required |
| K4 | Absence granularity (signal vs noise) | L3 | Configurable time windows |
| K5 | Posterior distribution computation cost | L6 | Batch sampling, caching |

---

## Anti-Patterns (Explicitly Forbidden)

| Pattern | Why Forbidden | What To Do Instead |
|---------|---------------|-------------------|
| End-to-end LLM fine-tuning | Smuggles inference | Use embeddings as coordinates only |
| Reinforcement learning | Implies reward/preference | Surface options without ranking |
| AutoML / AutoClustering | Opacity violates forensic traceability | Explicit algorithms, logged parameters |
| Threshold-based decisions | Hides uncertainty | Return raw scores, let human/frontend decide |
| Point estimates from posteriors | Hides distribution shape | Return full posterior + HDI |

---

## Implementation Checklist

### Phase 1: Coordinate Transforms (L2)
- [ ] Integrate sentence-transformers for embeddings
- [ ] Add embedding to `NormalizedFragment` as `embedding_vector`
- [ ] Compute pairwise distances, store in `DuplicateInfo.similarity_score`
- [ ] Do NOT set `DuplicateInfo.status` from ML alone

### Phase 2: Graph Topology (L3)
- [ ] Build NetworkX graph from fragment co-occurrence
- [ ] Store graph edges in `ThreadStateSnapshot.relations`
- [ ] Compute connected components for thread candidates
- [ ] Do NOT compute centrality or importance

### Phase 3: Timeline Alignment (L3)
- [ ] Integrate tslearn for DTW alignment
- [ ] Compute alignment distances between source timelines
- [ ] Store alignment path in divergence metadata
- [ ] Do NOT infer "who reported first" as authority

### Phase 4: Clustering (L3)
- [ ] Integrate hdbscan for fragment grouping
- [ ] Preserve noise labels as UNASSIGNED
- [ ] Store cluster probabilities (soft clustering)
- [ ] Do NOT force all fragments into clusters

### Phase 5: Uncertainty Surfacing (L6)
- [ ] Integrate PyMC for observability metrics
- [ ] Compute posterior distributions, not point estimates
- [ ] Store credible intervals in `MetricPoint`
- [ ] Do NOT emit binary anomaly flags

---

## Summary

**ML is instrumentation, not judgment.**

Every library serves as a **probe** that measures geometry, distance, alignment, or distribution. The measurements cross layer boundaries as immutable data. The **interpretation** of those measurements happens in the frontend or by human operators—never in the backend.

```
┌─────────────────────────────────────────────────────────────┐
│                    THE FUNDAMENTAL RULE                     │
├─────────────────────────────────────────────────────────────┤
│  If an ML output cannot be serialized as an immutable       │
│  contract without losing information, it is FORBIDDEN.      │
│                                                             │
│  Distributions serialize. Decisions do not.                 │
└─────────────────────────────────────────────────────────────┘
```
