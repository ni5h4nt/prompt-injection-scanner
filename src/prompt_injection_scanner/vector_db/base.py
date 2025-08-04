"""
Base vector database interface - Strategy pattern
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Search result from vector database"""
    similarity: float
    text: str
    metadata: dict


class VectorDB(ABC):
    """
    Abstract base class for vector databases
    Strategy pattern for pluggable vector DB implementations
    """
    
    @abstractmethod
    async def search(self, embedding: List[float], limit: int = 5) -> List[SearchResult]:
        """Search for similar embeddings"""
        pass
    
    @abstractmethod
    async def add(self, embedding: List[float], text: str, metadata: dict = None) -> str:
        """Add embedding to database"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if database is healthy"""
        pass
    
    async def close(self):
        """Close database connection - optional override"""
        pass