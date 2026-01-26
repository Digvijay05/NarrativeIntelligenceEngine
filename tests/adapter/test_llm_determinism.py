"""
LLM Determinism Tests
=====================

Tests verifying deterministic envelope for LLM executor.

INVARIANTS TESTED:
1. Same (snapshot, seed) → identical overlay
2. Different seeds MAY produce different overlays  
3. Prompt is pure function of snapshot
4. Provider failure → explicit error overlay
"""

import pytest
import json
import hashlib
from datetime import datetime, timezone

from adapter.llm_executor import LLMModelExecutor
from adapter.prompts import CanonicalPrompt
from adapter.providers.mock import MockProvider
from adapter.providers.base import ProviderErrorCode, InvocationParams
from adapter.contracts import (
    ModelAnalysisRequest,
    NarrativeSnapshotInput,
    FragmentBatchInput,
)


def make_fragment_batch(
    fragment_ids=("frag_1", "frag_2"),
    contents=("Content A", "Content B")
) -> FragmentBatchInput:
    """Factory for test FragmentBatchInput."""
    n = len(fragment_ids)
    return FragmentBatchInput(
        batch_id="test_batch_1",
        fragment_ids=tuple(fragment_ids),
        fragment_contents=tuple(contents),
        fragment_timestamps=tuple(
            datetime(2026, 1, 1, 10 + i, 0, tzinfo=timezone.utc)
            for i in range(n)
        ),
        topic_ids=tuple(("topic_1",) for _ in range(n)),
        entity_ids=tuple(() for _ in range(n)),
        source_ids=tuple(f"src_{chr(97+i)}" for i in range(n))
    )


def make_snapshot(thread_id: str = "test_thread") -> NarrativeSnapshotInput:
    """Factory for test NarrativeSnapshotInput."""
    return NarrativeSnapshotInput(
        snapshot_id="snap_test_1",
        snapshot_version="v1",
        captured_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        thread_id=thread_id,
        thread_lifecycle="active",
        thread_topics=("topic_1",),
        fragments=make_fragment_batch(),
        existing_annotations=()
    )


class TestPromptDeterminism:
    """Test that prompts are pure functions of snapshot data."""
    
    def test_same_snapshot_same_prompt_hash(self):
        """Same snapshot → identical prompt_hash across invocations."""
        snapshot = make_snapshot()
        
        prompts = []
        for _ in range(10):
            prompt = CanonicalPrompt.create("divergence_scoring", snapshot)
            prompts.append(prompt.prompt_hash)
        
        assert len(set(prompts)) == 1, "Prompt hash should be identical across invocations"
    
    def test_different_snapshot_different_hash(self):
        """Different snapshot → different prompt_hash."""
        snapshot1 = make_snapshot(thread_id="thread_1")
        snapshot2 = make_snapshot(thread_id="thread_2")
        
        prompt1 = CanonicalPrompt.create("divergence_scoring", snapshot1)
        prompt2 = CanonicalPrompt.create("divergence_scoring", snapshot2)
        
        assert prompt1.prompt_hash != prompt2.prompt_hash
    
    def test_different_task_type_different_hash(self):
        """Same snapshot + different task → different prompt_hash."""
        snapshot = make_snapshot()
        
        prompt1 = CanonicalPrompt.create("divergence_scoring", snapshot)
        prompt2 = CanonicalPrompt.create("coherence_analysis", snapshot)
        
        assert prompt1.prompt_hash != prompt2.prompt_hash


class TestLLMExecutorDeterminism:
    """Test deterministic envelope for LLM executor."""
    
    @pytest.fixture
    def mock_executor(self):
        """Create executor with mock provider."""
        provider = MockProvider(latency_ms=10.0)
        return LLMModelExecutor(provider=provider, temperature=0.0)
    
    def test_same_seed_identical_response(self, mock_executor):
        """Same (snapshot, seed) → byte-identical response."""
        request = ModelAnalysisRequest(
            request_id="test_req_1",
            request_type="divergence_scoring",
            snapshot=make_snapshot(),
            random_seed=42
        )
        
        responses = []
        for _ in range(5):
            response = mock_executor.execute(request, random_seed=42)
            serialized = self._serialize_response(response)
            responses.append(serialized)
        
        assert len(set(responses)) == 1, "Responses should be identical for same seed"
    
    def test_different_seed_may_differ(self, mock_executor):
        """Different seeds MAY produce different overlays."""
        request = ModelAnalysisRequest(
            request_id="test_req_2",
            request_type="divergence_scoring",
            snapshot=make_snapshot(),
            random_seed=42
        )
        
        response_42 = mock_executor.execute(request, random_seed=42)
        response_99 = mock_executor.execute(request, random_seed=99)
        
        assert response_42.success
        assert response_99.success
        assert response_42.scores is not None
        assert response_99.scores is not None
    
    def test_version_info_captured(self, mock_executor):
        """Model version info is captured for traceability."""
        version = mock_executor.get_version()
        
        assert version.model_id is not None
        assert version.model_version is not None
        assert version.config_hash is not None
    
    def _serialize_response(self, response) -> str:
        """Serialize response excluding non-deterministic timing fields."""
        return json.dumps({
            "success": response.success,
            "scores": [(s.score_type, s.value) for s in response.scores] if response.scores else [],
            "annotations": [(a.annotation_type, a.value) for a in response.annotations] if response.annotations else [],
        }, sort_keys=True)


class TestProviderFailureHandling:
    """Test that provider failures become explicit error overlays."""
    
    def test_timeout_becomes_error_overlay(self):
        """Provider timeout → explicit TIMEOUT error."""
        provider = MockProvider(failure_mode=ProviderErrorCode.TIMEOUT)
        executor = LLMModelExecutor(provider=provider)
        
        request = ModelAnalysisRequest(
            request_id="test_timeout",
            request_type="divergence_scoring",
            snapshot=make_snapshot(),
            random_seed=42
        )
        
        response = executor.execute(request, random_seed=42)
        
        assert not response.success
        assert response.error is not None
        assert "TIMEOUT" in str(response.error.error_code)
    
    def test_rate_limit_becomes_error_overlay(self):
        """Provider rate limit → explicit error overlay."""
        provider = MockProvider(failure_mode=ProviderErrorCode.RATE_LIMITED)
        executor = LLMModelExecutor(provider=provider)
        
        request = ModelAnalysisRequest(
            request_id="test_rate_limit",
            request_type="divergence_scoring",
            snapshot=make_snapshot(),
            random_seed=42
        )
        
        response = executor.execute(request, random_seed=42)
        
        assert not response.success
        assert response.error is not None
    
    def test_content_filter_becomes_refusal(self):
        """Provider content filter → MODEL_REFUSAL error."""
        provider = MockProvider(failure_mode=ProviderErrorCode.CONTENT_FILTERED)
        executor = LLMModelExecutor(provider=provider)
        
        request = ModelAnalysisRequest(
            request_id="test_filter",
            request_type="divergence_scoring",
            snapshot=make_snapshot(),
            random_seed=42
        )
        
        response = executor.execute(request, random_seed=42)
        
        assert not response.success
        assert response.error is not None
