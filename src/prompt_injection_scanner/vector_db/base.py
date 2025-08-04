"""Base vector database interface - Strategy pattern."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class SearchResult:
    """Search result from vector database."""

    similarity: float
    text: str
    metadata: dict


class VectorDB(ABC):
    """Abstract base class for vector databases.

    Strategy pattern for pluggable vector DB implementations.
    """

    @abstractmethod
    async def search(
        self, embedding: List[float], limit: int = 5
    ) -> List[SearchResult]:
        """Search for similar embeddings (legacy method)."""
        pass

    @abstractmethod
    async def similarity_search(
        self, embedding: List[float], threshold: float = 0.75, k: int = 5
    ) -> List[SearchResult]:
        """Search for embeddings above similarity threshold."""
        pass

    @abstractmethod
    async def add(
        self, embedding: List[float], text: str, metadata: dict = None
    ) -> str:
        """Add embedding to database."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if database is healthy."""
        pass

    async def close(self):
        """Close database connection - optional override."""
        pass
