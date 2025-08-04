"""
Vector database integrations with clean abstractions
"""

from .base import VectorDB, SearchResult
from .factory import create_vector_db

__all__ = ["VectorDB", "SearchResult", "create_vector_db"]