"""
LLM Providers Package
=====================

Provider implementations for LLM invocation.

Available providers:
- MockProvider: Deterministic mock for testing
- LocalModelProvider: Local sentence-transformers (NO API CALLS)
"""

from .base import (
    LLMProvider,
    ProviderVersion,
    ProviderResponse,
    ProviderErrorCode,
    InvocationParams,
)
from .mock import MockProvider

__all__ = [
    'LLMProvider',
    'ProviderVersion', 
    'ProviderResponse',
    'ProviderErrorCode',
    'InvocationParams',
    'MockProvider',
]

# LocalModelProvider imported separately to avoid sentence-transformers dependency
# Use: from adapter.providers.local import LocalModelProvider

