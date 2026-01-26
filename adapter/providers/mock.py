"""
Mock LLM Provider
=================

Deterministic mock provider for testing.

GUARANTEES:
- Same (prompt_hash, seed) → identical response
- Explicit failure modes can be triggered
- No external dependencies
"""

from __future__ import annotations
import hashlib
import time
from datetime import datetime, timezone
from typing import Optional

from .base import (
    LLMProvider,
    ProviderVersion,
    ProviderResponse,
    ProviderErrorCode,
    InvocationParams,
)


class MockProvider(LLMProvider):
    """
    Deterministic mock provider for testing.
    
    Response is derived from hash(prompt + seed) for reproducibility.
    """
    
    def __init__(
        self,
        latency_ms: float = 50.0,
        failure_mode: Optional[ProviderErrorCode] = None
    ):
        """
        Args:
            latency_ms: Simulated latency
            failure_mode: If set, all invocations fail with this error
        """
        self._latency_ms = latency_ms
        self._failure_mode = failure_mode
        self._version = ProviderVersion(
            provider_id="mock",
            model_id="mock-deterministic-v1",
            api_version="1.0.0",
            supports_seed=True
        )
    
    @property
    def provider_id(self) -> str:
        return "mock"
    
    def get_version(self) -> ProviderVersion:
        return self._version
    
    def invoke(
        self,
        prompt: str,
        params: InvocationParams
    ) -> ProviderResponse:
        """
        Deterministic mock invocation.
        
        Response content is derived from prompt hash + seed.
        """
        invoked_at = datetime.now(timezone.utc)
        
        # Simulate latency
        time.sleep(self._latency_ms / 1000.0)
        
        # Check for configured failure mode
        if self._failure_mode is not None:
            return ProviderResponse(
                success=False,
                error_code=self._failure_mode,
                error_message=f"Mock provider configured to fail: {self._failure_mode.value}",
                provider_version=self._version,
                invoked_at=invoked_at,
                latency_ms=self._latency_ms,
                seed_used=params.seed,
                temperature_used=params.temperature
            )
        
        # Generate deterministic response from prompt + seed
        content = self._generate_deterministic_response(prompt, params.seed)
        
        return ProviderResponse(
            success=True,
            content=content,
            provider_version=self._version,
            invoked_at=invoked_at,
            latency_ms=self._latency_ms,
            seed_used=params.seed,
            temperature_used=params.temperature
        )
    
    def _generate_deterministic_response(self, prompt: str, seed: int) -> str:
        """
        Generate deterministic mock response.
        
        Same (prompt, seed) → same response.
        """
        # Hash prompt + seed for deterministic result
        content_hash = hashlib.sha256(
            f"{prompt}|{seed}".encode()
        ).hexdigest()[:16]
        
        # Generate mock analysis response
        # This structure matches what the LLM executor expects to parse
        response = {
            "analysis_type": "mock_analysis",
            "deterministic_hash": content_hash,
            "annotations": [
                {
                    "type": "divergence_indicator",
                    "confidence": 0.7,
                    "evidence": "Derived from content hash"
                }
            ],
            "scores": [
                {
                    "name": "coherence",
                    "value": 0.85,
                    "uncertainty": 0.1
                },
                {
                    "name": "divergence_risk", 
                    "value": 0.3,
                    "uncertainty": 0.15
                }
            ],
            "seed_used": seed
        }
        
        import json
        return json.dumps(response, sort_keys=True)
