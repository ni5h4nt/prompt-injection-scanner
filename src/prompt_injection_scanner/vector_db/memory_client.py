"""
In-memory vector database for testing and development
Simple implementation following KISS principle
"""

from typing import List, Dict, Any
import math
import structlog

from .base import VectorDB, SearchResult

logger = structlog.get_logger(__name__)


class MemoryVectorDB(VectorDB):
    """
    Simple in-memory vector database for testing
    Uses cosine similarity for search
    """
    
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.next_id = 1
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    async def search(self, embedding: List[float], limit: int = 5) -> List[SearchResult]:
        """Search for similar embeddings using cosine similarity"""
        if not self.documents:
            return []
        
        # Calculate similarities
        similarities = []
        for doc in self.documents:
            similarity = self._cosine_similarity(embedding, doc['embedding'])
            similarities.append((similarity, doc))
        
        # Sort by similarity (descending) and take top results
        similarities.sort(key=lambda x: x[0], reverse=True)
        top_results = similarities[:limit]
        
        # Convert to SearchResult objects
        results = []
        for similarity, doc in top_results:
            results.append(SearchResult(
                similarity=similarity,
                text=doc['text'],
                metadata=doc['metadata']
            ))
        
        logger.debug("memory_db_search", query_results=len(results))
        return results
    
    async def add(self, embedding: List[float], text: str, metadata: dict = None) -> str:
        """Add embedding to in-memory storage"""
        doc_id = f"mem_{self.next_id}"
        self.next_id += 1
        
        document = {
            'id': doc_id,
            'embedding': embedding,
            'text': text,
            'metadata': metadata or {}
        }
        
        self.documents.append(document)
        logger.debug("memory_db_add", doc_id=doc_id, total_docs=len(self.documents))
        return doc_id
    
    async def health_check(self) -> bool:
        """Memory DB is always healthy"""
        return True
    
    async def close(self):
        """Clear memory"""
        self.documents.clear()
        logger.debug("memory_db_cleared")
    
    def size(self) -> int:
        """Get number of documents stored"""
        return len(self.documents)