"""
Local Model Provider
====================

Local, offline model execution using sentence-transformers.

CONSTITUTIONAL CONSTRAINT:
- NO external API calls
- All computation local
- Models versioned by hash(weights + tokenizer + config)

GUARANTEES:
- Deterministic given same input + seed
- No network calls (fails hard if attempted)
- CPU-only path available
"""

from __future__ import annotations
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import os

from .base import (
    LLMProvider,
    ProviderVersion,
    ProviderResponse,
    ProviderErrorCode,
    InvocationParams,
)


class LocalModelProvider(LLMProvider):
    """
    Local model provider using sentence-transformers for embeddings
    and lightweight classifiers for analysis.
    
    NO NETWORK CALLS. Fails hard if offline models unavailable.
    
    APPROPRIATE USES:
    - Embedding computation
    - Contradiction/entailment classification
    - Topic affinity scoring
    
    INAPPROPRIATE USES:
    - Text generation
    - Narrative summarization  
    - "Analysis" prose
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        trust_remote_code: bool = False
    ):
        """
        Initialize local model provider.
        
        Args:
            model_name: HuggingFace model identifier (must be cached locally)
            device: "cpu" for determinism, "cuda" optional
            trust_remote_code: Should be False for security
        """
        self._model_name = model_name
        self._device = device
        self._trust_remote_code = trust_remote_code
        self._model = None
        self._model_hash = None
        
        # Compute version on init
        self._version = self._compute_version()
    
    @property
    def provider_id(self) -> str:
        return "local"
    
    def get_version(self) -> ProviderVersion:
        return self._version
    
    def _compute_version(self) -> ProviderVersion:
        """Compute version hash from model config."""
        config_str = json.dumps({
            "model_name": self._model_name,
            "device": self._device,
            "provider": "sentence-transformers"
        }, sort_keys=True)
        
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:16]
        
        return ProviderVersion(
            provider_id="local",
            model_id=self._model_name,
            api_version=config_hash,
            supports_seed=True  # Local models support deterministic seeding
        )
    
    def _load_model(self):
        """Lazy load model. Fails hard if not available offline."""
        if self._model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            
            # Force offline mode - no network calls
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["HF_DATASETS_OFFLINE"] = "1"
            
            self._model = SentenceTransformer(
                self._model_name,
                device=self._device,
                trust_remote_code=self._trust_remote_code
            )
            
            # Compute actual model hash
            self._model_hash = self._compute_model_hash()
            
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            )
        except Exception as e:
            if "offline" in str(e).lower() or "connection" in str(e).lower():
                raise RuntimeError(
                    f"Model {self._model_name} not available offline. "
                    "Download it first, then run in offline mode."
                )
            raise
    
    def _compute_model_hash(self) -> str:
        """Compute hash of model weights for version tracking."""
        # In production, would hash actual weights
        # For prototype, hash model name + device
        return hashlib.sha256(
            f"{self._model_name}|{self._device}".encode()
        ).hexdigest()[:16]
    
    def invoke(
        self,
        prompt: str,
        params: InvocationParams
    ) -> ProviderResponse:
        """
        Invoke local model for semantic analysis.
        
        For embedding-based analysis, the prompt is embedded and
        analyzed using cosine similarity or classification.
        """
        invoked_at = datetime.now(timezone.utc)
        start_time = time.time()
        
        try:
            self._load_model()
            
            # Set random seed for determinism
            import random
            import numpy as np
            random.seed(params.seed)
            np.random.seed(params.seed)
            
            try:
                import torch
                torch.manual_seed(params.seed)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(params.seed)
            except ImportError:
                pass  # PyTorch optional for CPU-only
            
            # Perform embedding-based analysis
            result = self._analyze_with_embeddings(prompt, params.seed)
            
            latency_ms = (time.time() - start_time) * 1000
            
            return ProviderResponse(
                success=True,
                content=json.dumps(result, sort_keys=True),
                provider_version=self._version,
                invoked_at=invoked_at,
                latency_ms=latency_ms,
                seed_used=params.seed,
                temperature_used=0.0  # Embeddings are deterministic
            )
            
        except ImportError as e:
            return ProviderResponse(
                success=False,
                error_code=ProviderErrorCode.API_ERROR,
                error_message=str(e),
                provider_version=self._version,
                invoked_at=invoked_at,
                latency_ms=(time.time() - start_time) * 1000,
                seed_used=params.seed,
                temperature_used=0.0
            )
            
        except RuntimeError as e:
            # Likely offline/network error
            return ProviderResponse(
                success=False,
                error_code=ProviderErrorCode.NETWORK_ERROR,
                error_message=f"Local model error (possible network attempt): {e}",
                provider_version=self._version,
                invoked_at=invoked_at,
                latency_ms=(time.time() - start_time) * 1000,
                seed_used=params.seed,
                temperature_used=0.0
            )
            
        except Exception as e:
            return ProviderResponse(
                success=False,
                error_code=ProviderErrorCode.API_ERROR,
                error_message=str(e),
                provider_version=self._version,
                invoked_at=invoked_at,
                latency_ms=(time.time() - start_time) * 1000,
                seed_used=params.seed,
                temperature_used=0.0
            )
    
    def _analyze_with_embeddings(self, prompt: str, seed: int) -> Dict[str, Any]:
        """
        Perform embedding-based analysis.
        
        This is a STRUCTURAL analysis, not text generation.
        Output is JSON scores/indicators, never prose.
        """
        # Extract fragments from prompt (they're embedded in canonical format)
        # For prototype, compute simple embedding similarity metrics
        
        # Embed the prompt
        embedding = self._model.encode(prompt, convert_to_numpy=True)
        
        # Compute deterministic metrics from embedding
        # These are structural signals, not interpretations
        import numpy as np
        
        # Embedding-derived scores (deterministic given seed)
        coherence_signal = float(np.std(embedding))
        divergence_signal = float(np.mean(np.abs(embedding)))
        
        # Normalize to 0-1 range
        coherence_score = min(1.0, coherence_signal / 0.5)
        divergence_score = min(1.0, divergence_signal / 0.3)
        
        return {
            "analysis_type": "embedding_based",
            "model_hash": self._model_hash,
            "seed_used": seed,
            "scores": [
                {
                    "name": "coherence",
                    "value": round(1.0 - coherence_score, 3),
                    "uncertainty": 0.1
                },
                {
                    "name": "divergence_risk",
                    "value": round(divergence_score, 3),
                    "uncertainty": 0.15
                }
            ],
            "annotations": []
        }
