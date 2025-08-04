"""
Vector database integrations with clean abstractions
"""

from .base import SearchResult, VectorDB
from .factory import create_vector_db
from .milvus_client import MilvusClient

__all__ = ["VectorDB", "SearchResult", "create_vector_db", "MilvusClient"]
