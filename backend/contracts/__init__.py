"""
Contracts Module

This module defines the explicit interfaces and data transfer objects
that form the contracts between layers. All inter-layer communication
MUST use these contracts. No layer may import implementation details
from another layer.

DESIGN PRINCIPLES:
==================
1. All contract types are immutable (frozen dataclasses)
2. All contracts include explicit error states
3. No optional fields that could lead to ambiguous behavior
4. All timestamps use UTC and are never mutated
5. Hash-based identity for deduplication and integrity verification
"""
