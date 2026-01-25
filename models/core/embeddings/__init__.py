"""
Embeddings Subpackage

Graph and sequence embeddings for representation learning.
"""

from .graph_embeddings import GraphEmbedder
from .sequence_embeddings import SequenceEmbedder

__all__ = ['GraphEmbedder', 'SequenceEmbedder']
