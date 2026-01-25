"""
Models Package - Narrative Intelligence Engine

This package implements the AI/ML model layer with strict separation
between 5 phases. Each phase is an isolated subsystem that communicates
only through explicit data contracts.

PHASE STRUCTURE:
================

1. DATA FOUNDATION (models/data/)
   - Preprocessing pipelines
   - Annotation & tagging
   - Versioned data lineage
   - MUST NOT: learn, infer, predict

2. CORE AI MODELS (models/core/)
   - Knowledge graph construction
   - Embedding & representation learning
   - Multi-task learning heads
   - MUST NOT: temporal prediction, inference, validation

3. TEMPORAL INFERENCE (models/temporal/)
   - State prediction
   - Uncertainty modeling
   - Temporal alignment
   - MUST NOT: train models, compute metrics, serve

4. VALIDATION (models/validation/)
   - Metrics computation
   - Error categorization
   - Drift detection
   - MUST NOT: mutate models, train, infer

5. INFERENCE & SERVING (models/inference/)
   - Real-time & batch serving
   - Caching & optimization
   - Version-aware inference
   - MUST NOT: train, validate, preprocess

CROSS-CUTTING:
==============
- contracts/ - Explicit data contracts between phases
- versioning/ - Model versioning and replay

CONSTRAINTS ENFORCED:
=====================
- No shared mutable state
- All inter-phase data is immutable
- Temporal logic isolated in Phase 3
- All functions deterministic and replay-safe
"""
