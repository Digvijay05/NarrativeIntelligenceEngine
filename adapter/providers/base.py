"""
LLM Provider Abstraction Layer
==============================

Abstract interface for LLM providers (Anthropic, OpenAI, etc.)

BOUNDARY ENFORCEMENT:
- Providers are stateless invocation handlers
- All stochasticity is captured via seed
- Failures are explicit, never silent
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class ProviderErrorCode(Enum):
    """Explicit failure codes for LLM invocations."""
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_RESPONSE = "invalid_response"
    CONTENT_FILTERED = "content_filtered"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"
    SEED_NOT_SUPPORTED = "seed_not_supported"


@dataclass(frozen=True)
class ProviderVersion:
    """
    Immutable provider version info.
    
    WHY FROZEN: Provider version is part of the deterministic envelope.
    Changes imply different outputs, so must be tracked.
    """
    provider_id: str       # "anthropic" | "openai" | "mock"
    model_id: str          # "claude-3-sonnet" | "gpt-4"
    api_version: str       # Provider API version
    supports_seed: bool    # Whether seeded sampling is available
    

@dataclass(frozen=True)
class ProviderResponse:
    """
    Immutable response from LLM provider.
    
    INVARIANT: Either (success=True, content set) or (success=False, error set)
    """
    success: bool
    content: Optional[str] = None
    
    # Failure info (only set if success=False)
    error_code: Optional[ProviderErrorCode] = None
    error_message: Optional[str] = None
    
    # Invocation metadata (always set)
    provider_version: Optional[ProviderVersion] = None
    invoked_at: Optional[datetime] = None
    latency_ms: float = 0.0
    
    # Seed tracking
    seed_used: Optional[int] = None
    temperature_used: float = 1.0
    
    def __post_init__(self):
        if self.success and self.content is None:
            raise ValueError("Successful response must have content")
        if not self.success and self.error_code is None:
            raise ValueError("Failed response must have error_code")


@dataclass(frozen=True)
class InvocationParams:
    """
    Frozen invocation parameters.
    
    WHY FROZEN: Part of deterministic envelope.
    Same params + same prompt = same result (where provider supports seed).
    """
    seed: int
    temperature: float = 0.0  # 0.0 for maximum determinism
    max_tokens: int = 4096
    timeout_seconds: float = 30.0


class LLMProvider(ABC):
    """
    Abstract LLM provider interface.
    
    GUARANTEES:
    - Invocations are stateless
    - Failures are explicit ProviderResponse with error_code
    - Seed is passed through (whether honored is provider-dependent)
    
    EXPLICIT FAILURE STATES:
    - TIMEOUT: Invocation exceeded timeout_seconds
    - RATE_LIMITED: Provider rejected due to rate limits
    - INVALID_RESPONSE: Response couldn't be parsed
    - CONTENT_FILTERED: Response blocked by safety filter
    - API_ERROR: Provider returned error status
    - NETWORK_ERROR: Connection failed
    - SEED_NOT_SUPPORTED: Seed requested but provider doesn't support
    """
    
    @abstractmethod
    def invoke(
        self,
        prompt: str,
        params: InvocationParams
    ) -> ProviderResponse:
        """
        Invoke the LLM with given prompt and parameters.
        
        MUST return ProviderResponse, never raise exceptions.
        All failures become explicit error responses.
        """
        pass
    
    @abstractmethod
    def get_version(self) -> ProviderVersion:
        """Get provider version info for deterministic envelope."""
        pass
    
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier."""
        pass
