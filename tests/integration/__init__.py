"""
Integration Tests Package

Comprehensive test harness for backend-model boundary validation.

TEST AXIOMS:
=============
1. Determinism: same input + version = byte-identical output
2. One-way authority: model cannot mutate backend state
3. Explicit failure: no silent fallbacks
"""
