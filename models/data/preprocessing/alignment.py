"""
Alignment Engine

Performs semantic similarity clustering and temporal coherence scoring.

BOUNDARY ENFORCEMENT:
- Consumes RawDataPoint contracts
- Produces alignment scores
- NO learning, NO inference
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from datetime import datetime
import hashlib
import math

# Import ONLY from contracts
from ...contracts.data_contracts import RawDataPoint, DataQuality


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class AlignmentConfig:
    """Configuration for alignment engine."""
    similarity_threshold: float = 0.7
    temporal_window_seconds: int = 86400  # 24 hours
    min_cluster_size: int = 2
    coherence_decay_rate: float = 0.1


# =============================================================================
# SIMILARITY COMPUTATION (Deterministic)
# =============================================================================

class SimilarityComputer:
    """
    Compute semantic similarity between text payloads.
    
    Uses deterministic methods (no probabilistic models).
    Same input always produces same output.
    """
    
    def __init__(self):
        # Common words for TF-IDF weighting (simplified)
        self._stopwords = frozenset({
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are',
            'were', 'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did'
        })
    
    def tokenize(self, text: str) -> Tuple[str, ...]:
        """Tokenize text into normalized words."""
        import re
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        return tuple(w for w in words if w not in self._stopwords)
    
    def compute_jaccard(
        self, 
        tokens_a: Tuple[str, ...], 
        tokens_b: Tuple[str, ...]
    ) -> float:
        """Compute Jaccard similarity between token sets."""
        set_a = frozenset(tokens_a)
        set_b = frozenset(tokens_b)
        
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union
    
    def compute_cosine(
        self, 
        tokens_a: Tuple[str, ...], 
        tokens_b: Tuple[str, ...]
    ) -> float:
        """Compute cosine similarity using term frequency."""
        # Build term frequency vectors
        all_terms = sorted(set(tokens_a) | set(tokens_b))
        if not all_terms:
            return 0.0
        
        vec_a = [tokens_a.count(t) for t in all_terms]
        vec_b = [tokens_b.count(t) for t in all_terms]
        
        # Compute cosine
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def compute_similarity(
        self, 
        text_a: str, 
        text_b: str
    ) -> float:
        """
        Compute overall similarity between two texts.
        
        Combines Jaccard and cosine for robust similarity.
        """
        tokens_a = self.tokenize(text_a)
        tokens_b = self.tokenize(text_b)
        
        jaccard = self.compute_jaccard(tokens_a, tokens_b)
        cosine = self.compute_cosine(tokens_a, tokens_b)
        
        # Weighted combination
        return 0.4 * jaccard + 0.6 * cosine


# =============================================================================
# TEMPORAL COHERENCE
# =============================================================================

class TemporalCoherenceScorer:
    """
    Score temporal coherence of data sequences.
    
    Measures how well data points flow in time.
    """
    
    def __init__(self, config: AlignmentConfig):
        self._config = config
    
    def score_sequence(
        self, 
        timestamps: List[datetime]
    ) -> float:
        """
        Score temporal coherence of a timestamp sequence.
        
        Returns 0.0 to 1.0, where 1.0 is perfectly coherent.
        """
        if len(timestamps) < 2:
            return 1.0
        
        sorted_ts = sorted(timestamps)
        gaps = []
        
        for i in range(1, len(sorted_ts)):
            gap = (sorted_ts[i] - sorted_ts[i-1]).total_seconds()
            gaps.append(gap)
        
        if not gaps:
            return 1.0
        
        # Compute coherence based on gap regularity
        avg_gap = sum(gaps) / len(gaps)
        if avg_gap == 0:
            return 1.0
        
        # Variance penalty
        variance = sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)
        std_dev = math.sqrt(variance)
        
        # Normalize by average gap
        coefficient_of_variation = std_dev / avg_gap if avg_gap > 0 else 0
        
        # Score: lower variance = higher coherence
        coherence = 1.0 / (1.0 + coefficient_of_variation)
        
        return min(1.0, max(0.0, coherence))
    
    def score_pair(
        self, 
        ts_a: datetime, 
        ts_b: datetime
    ) -> float:
        """Score coherence between two timestamps."""
        gap = abs((ts_b - ts_a).total_seconds())
        
        # Apply exponential decay based on gap
        decay = math.exp(-self._config.coherence_decay_rate * gap / self._config.temporal_window_seconds)
        
        return decay


# =============================================================================
# ALIGNMENT ENGINE
# =============================================================================

@dataclass
class AlignmentScore:
    """Score from alignment computation."""
    data_id_a: str
    data_id_b: str
    semantic_similarity: float
    temporal_coherence: float
    combined_score: float
    computed_at: datetime


@dataclass
class ClusterResult:
    """Result of clustering aligned data."""
    cluster_id: str
    member_ids: Tuple[str, ...]
    centroid_id: str
    avg_similarity: float
    temporal_span_seconds: float


class AlignmentEngine:
    """
    Engine for aligning data points by semantic similarity
    and temporal coherence.
    
    BOUNDARY ENFORCEMENT:
    - Consumes RawDataPoint
    - Produces AlignmentScore, ClusterResult
    - NO learning, NO inference
    """
    
    def __init__(self, config: Optional[AlignmentConfig] = None):
        self._config = config or AlignmentConfig()
        self._similarity = SimilarityComputer()
        self._coherence = TemporalCoherenceScorer(self._config)
    
    def compute_alignment(
        self, 
        data_a: RawDataPoint, 
        data_b: RawDataPoint
    ) -> AlignmentScore:
        """
        Compute alignment score between two data points.
        
        Combines semantic similarity and temporal coherence.
        """
        semantic_sim = self._similarity.compute_similarity(
            data_a.payload, 
            data_b.payload
        )
        temporal_coh = self._coherence.score_pair(
            data_a.timestamp, 
            data_b.timestamp
        )
        
        # Combined score (weighted average)
        combined = 0.6 * semantic_sim + 0.4 * temporal_coh
        
        return AlignmentScore(
            data_id_a=data_a.data_id,
            data_id_b=data_b.data_id,
            semantic_similarity=semantic_sim,
            temporal_coherence=temporal_coh,
            combined_score=combined,
            computed_at=datetime.now()
        )
    
    def compute_all_alignments(
        self, 
        data_points: List[RawDataPoint]
    ) -> List[AlignmentScore]:
        """Compute all pairwise alignments."""
        alignments = []
        
        for i in range(len(data_points)):
            for j in range(i + 1, len(data_points)):
                score = self.compute_alignment(data_points[i], data_points[j])
                if score.combined_score >= self._config.similarity_threshold:
                    alignments.append(score)
        
        return alignments
    
    def cluster_by_similarity(
        self, 
        data_points: List[RawDataPoint],
        alignments: List[AlignmentScore]
    ) -> List[ClusterResult]:
        """
        Cluster data points based on alignment scores.
        
        Uses simple greedy clustering (deterministic).
        """
        # Build adjacency from alignments
        adjacency: Dict[str, set] = {}
        for dp in data_points:
            adjacency[dp.data_id] = set()
        
        for score in alignments:
            if score.combined_score >= self._config.similarity_threshold:
                adjacency[score.data_id_a].add(score.data_id_b)
                adjacency[score.data_id_b].add(score.data_id_a)
        
        # Greedy clustering
        clusters = []
        assigned = set()
        
        # Sort data points by ID for determinism
        sorted_points = sorted(data_points, key=lambda x: x.data_id)
        point_map = {dp.data_id: dp for dp in data_points}
        
        for dp in sorted_points:
            if dp.data_id in assigned:
                continue
            
            # Start new cluster
            cluster_members = {dp.data_id}
            queue = list(adjacency[dp.data_id])
            
            while queue:
                neighbor_id = queue.pop(0)
                if neighbor_id not in assigned and neighbor_id not in cluster_members:
                    cluster_members.add(neighbor_id)
                    for next_neighbor in adjacency[neighbor_id]:
                        if next_neighbor not in cluster_members:
                            queue.append(next_neighbor)
            
            if len(cluster_members) >= self._config.min_cluster_size:
                assigned.update(cluster_members)
                
                # Compute cluster properties
                member_list = sorted(cluster_members)
                timestamps = [point_map[mid].timestamp for mid in member_list]
                
                time_span = 0.0
                if len(timestamps) > 1:
                    time_span = (max(timestamps) - min(timestamps)).total_seconds()
                
                # Cluster ID from content hash
                cluster_hash = hashlib.sha256(
                    '|'.join(member_list).encode()
                ).hexdigest()[:12]
                
                clusters.append(ClusterResult(
                    cluster_id=f"cluster_{cluster_hash}",
                    member_ids=tuple(member_list),
                    centroid_id=member_list[0],  # First member as centroid
                    avg_similarity=0.0,  # Would compute from alignments
                    temporal_span_seconds=time_span
                ))
        
        return clusters
