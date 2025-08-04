"""ChromaDB implementation - clean, simple integration
"""

from typing import List

import structlog

from .base import SearchResult, VectorDB

logger = structlog.get_logger(__name__)

# Optional import - graceful degradation
try:
    import chromadb
    from chromadb.config import Settings

    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    chromadb = None


class ChromaDBClient(VectorDB):
    """ChromaDB implementation - KISS principle"""

    def __init__(
        self,
        url: str = "http://localhost:8001",
        collection_name: str = "malicious_prompts",
    ):
        if not HAS_CHROMADB:
            raise ImportError(
                "chromadb not installed. Install with: pip install chromadb"
            )

        self.url = url
        self.collection_name = collection_name
        self.client = None
        self.collection = None

    async def _ensure_connected(self):
        """Lazy connection - YAGNI principle"""
        if self.client is None:
            try:
                self.client = chromadb.HttpClient(
                    host=self.url.split("://")[1].split(":")[0],
                    port=int(self.url.split(":")[-1]),
                )
                self.collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={
                        "description": "Malicious prompt patterns for injection detection"
                    },
                )
                logger.info(
                    "chromadb_connected", url=self.url, collection=self.collection_name
                )
            except Exception as e:
                logger.error("chromadb_connection_failed", error=str(e))
                raise

    async def search(
        self, embedding: List[float], limit: int = 5
    ) -> List[SearchResult]:
        """Search for similar embeddings (legacy method)"""
        return await self.similarity_search(embedding, threshold=0.0, k=limit)

    async def similarity_search(
        self, embedding: List[float], threshold: float = 0.75, k: int = 5
    ) -> List[SearchResult]:
        """Search for similar embeddings with similarity threshold"""
        await self._ensure_connected()

        try:
            results = self.collection.query(query_embeddings=[embedding], n_results=k)

            search_results = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    # Convert distance to similarity (ChromaDB uses cosine distance by default)
                    distance = results["distances"][0][i]
                    similarity = 1.0 - distance

                    # Only include results above threshold
                    if similarity >= threshold:
                        metadata = (
                            results["metadatas"][0][i]
                            if results["metadatas"][0]
                            else {}
                        )

                        search_results.append(
                            SearchResult(
                                similarity=similarity, text=doc, metadata=metadata
                            )
                        )

            logger.debug(
                "chromadb_similarity_search_completed",
                results_count=len(search_results),
                threshold=threshold,
            )
            return search_results

        except Exception as e:
            logger.error("chromadb_similarity_search_failed", error=str(e))
            return []

    async def add(
        self, embedding: List[float], text: str, metadata: dict = None
    ) -> str:
        """Add embedding to database"""
        await self._ensure_connected()

        try:
            doc_id = f"doc_{hash(text)}"  # Simple ID generation

            self.collection.add(
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata or {}],
                ids=[doc_id],
            )

            logger.info("chromadb_document_added", doc_id=doc_id)
            return doc_id

        except Exception as e:
            logger.error("chromadb_add_failed", error=str(e))
            raise

    async def health_check(self) -> bool:
        """Check if ChromaDB is healthy"""
        try:
            await self._ensure_connected()
            # Simple health check - get collection info
            info = self.collection.count()
            logger.debug("chromadb_health_check", document_count=info)
            return True
        except Exception as e:
            logger.warning("chromadb_health_check_failed", error=str(e))
            return False

    async def close(self):
        """Close connection"""
        if self.client:
            # ChromaDB HTTP client doesn't need explicit closing
            self.client = None
            self.collection = None
            logger.info("chromadb_connection_closed")
