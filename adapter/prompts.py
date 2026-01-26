"""
Canonical Prompt Generation
===========================

Pure functions for generating prompts from snapshot DTOs.

INVARIANT: Same snapshot → same prompt_hash
No UI context, no analyst hints, no runtime state.

WHY THIS MODULE:
Prompts are part of the deterministic envelope.
They must be reproducible from snapshot data alone.
"""

from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from typing import List, Optional

from .contracts import NarrativeSnapshotInput, FragmentBatchInput


@dataclass(frozen=True)
class CanonicalPrompt:
    """
    Frozen prompt with hash for deterministic tracking.
    
    INVARIANT: Same task_type + snapshot → same prompt_hash
    """
    task_type: str
    snapshot_hash: str
    prompt_text: str
    prompt_hash: str
    
    @staticmethod
    def create(task_type: str, snapshot: NarrativeSnapshotInput) -> 'CanonicalPrompt':
        """
        Factory method for creating canonical prompts.
        
        This is the ONLY way to create prompts.
        """
        prompt_text = PromptTemplates.render(task_type, snapshot)
        prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()
        
        return CanonicalPrompt(
            task_type=task_type,
            snapshot_hash=snapshot.content_hash(),
            prompt_text=prompt_text,
            prompt_hash=prompt_hash
        )


class PromptTemplates:
    """
    Prompt templates for each task type.
    
    All templates are pure functions of snapshot data.
    """
    
    @staticmethod
    def render(task_type: str, snapshot: NarrativeSnapshotInput) -> str:
        """Render prompt for given task type."""
        if task_type == "contradiction_detection":
            return PromptTemplates._contradiction_prompt(snapshot)
        elif task_type == "divergence_scoring":
            return PromptTemplates._divergence_prompt(snapshot)
        elif task_type == "coherence_analysis":
            return PromptTemplates._coherence_prompt(snapshot)
        elif task_type == "lifecycle_prediction":
            return PromptTemplates._lifecycle_prompt(snapshot)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    @staticmethod
    def _fragment_summary(fragments: FragmentBatchInput) -> str:
        """Canonical fragment summary for prompts."""
        lines = []
        for i, (fid, content, ts) in enumerate(zip(
            fragments.fragment_ids,
            fragments.fragment_contents,
            fragments.fragment_timestamps
        )):
            lines.append(f"[{i}] ID:{fid} TIME:{ts.isoformat()} CONTENT:{content}")
        return "\n".join(lines)
    
    @staticmethod
    def _contradiction_prompt(snapshot: NarrativeSnapshotInput) -> str:
        """Prompt for contradiction detection."""
        fragments = PromptTemplates._fragment_summary(snapshot.fragments)
        
        return f"""TASK: Contradiction Detection
THREAD_ID: {snapshot.thread_id}
LIFECYCLE: {snapshot.thread_lifecycle}

FRAGMENTS:
{fragments}

INSTRUCTIONS:
Analyze the fragments above for logical contradictions.
A contradiction exists when two fragments make mutually exclusive claims.
Do NOT infer meaning beyond what is explicitly stated.
Do NOT resolve contradictions - only detect and report them.

OUTPUT FORMAT (JSON):
{{
  "contradictions": [
    {{
      "fragment_a": "<id>",
      "fragment_b": "<id>",
      "claim_a": "<exact quote>",
      "claim_b": "<exact quote>",
      "confidence": <0.0-1.0>
    }}
  ]
}}"""

    @staticmethod
    def _divergence_prompt(snapshot: NarrativeSnapshotInput) -> str:
        """Prompt for divergence scoring."""
        fragments = PromptTemplates._fragment_summary(snapshot.fragments)
        
        return f"""TASK: Divergence Risk Scoring
THREAD_ID: {snapshot.thread_id}
LIFECYCLE: {snapshot.thread_lifecycle}

FRAGMENTS:
{fragments}

INSTRUCTIONS:
Assess the risk that this narrative thread is diverging into multiple sub-narratives.
Indicators include: conflicting sources, emerging sub-topics, temporal gaps.
Do NOT predict future divergence - only assess current state.

OUTPUT FORMAT (JSON):
{{
  "divergence_risk": <0.0-1.0>,
  "uncertainty": <0.0-1.0>,
  "indicators": [
    {{
      "type": "<indicator_type>",
      "evidence_fragments": ["<id>", ...],
      "description": "<brief description>"
    }}
  ]
}}"""

    @staticmethod
    def _coherence_prompt(snapshot: NarrativeSnapshotInput) -> str:
        """Prompt for temporal coherence analysis."""
        fragments = PromptTemplates._fragment_summary(snapshot.fragments)
        
        return f"""TASK: Temporal Coherence Analysis
THREAD_ID: {snapshot.thread_id}
LIFECYCLE: {snapshot.thread_lifecycle}

FRAGMENTS:
{fragments}

INSTRUCTIONS:
Analyze the temporal coherence of the fragment sequence.
Coherence measures: consistent timeline, causal ordering, absence of anachronisms.
Report gaps or inconsistencies without inferring causes.

OUTPUT FORMAT (JSON):
{{
  "coherence_score": <0.0-1.0>,
  "uncertainty": <0.0-1.0>,
  "gaps": [
    {{
      "between_fragments": ["<id_a>", "<id_b>"],
      "gap_type": "temporal|causal|topical",
      "severity": <0.0-1.0>
    }}
  ]
}}"""

    @staticmethod
    def _lifecycle_prompt(snapshot: NarrativeSnapshotInput) -> str:
        """Prompt for lifecycle state prediction."""
        fragments = PromptTemplates._fragment_summary(snapshot.fragments)
        
        return f"""TASK: Lifecycle State Assessment
THREAD_ID: {snapshot.thread_id}
CURRENT_LIFECYCLE: {snapshot.thread_lifecycle}

FRAGMENTS:
{fragments}

INSTRUCTIONS:
Assess the current lifecycle state of this narrative thread.
States: emerging, active, dormant, diverged, terminated
Base assessment ONLY on fragment evidence, not external knowledge.

OUTPUT FORMAT (JSON):
{{
  "assessed_state": "<state>",
  "confidence": <0.0-1.0>,
  "state_probabilities": {{
    "emerging": <0.0-1.0>,
    "active": <0.0-1.0>,
    "dormant": <0.0-1.0>,
    "diverged": <0.0-1.0>,
    "terminated": <0.0-1.0>
  }},
  "evidence": ["<fragment_id>", ...]
}}"""
