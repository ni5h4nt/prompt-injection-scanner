"""Milvus vector database implementation."""

import asyncio
from typing import Any, Dict, List, Optional

import structlog

from ..decorators import with_error_handling, with_logging
from .base import SearchResult, VectorDB

try:
    from pymilvus import (
        Collection,
        CollectionSchema,
        DataType,
        FieldSchema,
        connections,
        utility,
    )

    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False

logger = structlog.get_logger(__name__)


class MilvusClient(VectorDB):
    """Milvus vector database client implementation.

    High-performance, cloud-native vector database for production use.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "prompt_injections",
        dimension: int = 384,  # all-MiniLM-L6-v2 embedding dimension
        index_type: str = "IVF_FLAT",
        metric_type: str = "COSINE",
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs,
    ):
        if not MILVUS_AVAILABLE:
            raise ImportError(
                "Milvus client requires pymilvus. Install with: pip install pymilvus"
            )

        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.dimension = dimension
        self.index_type = index_type
        self.metric_type = metric_type
        self.username = username
        self.password = password
        self.connection_alias = f"milvus_{id(self)}"

        self._collection: Optional[Collection] = None
        self._connected = False

        logger.info(
            "milvus_client_init",
            host=host,
            port=port,
            collection=collection_name,
            dimension=dimension,
        )

    async def _connect(self):
        """Establish connection to Milvus"""
        if self._connected:
            return

        try:
            # Run connection in thread pool since pymilvus is sync
            await asyncio.get_event_loop().run_in_executor(None, self._sync_connect)
            self._connected = True
            logger.info("milvus_connected", alias=self.connection_alias)

        except Exception as e:
            logger.error(
                "milvus_connection_failed", host=self.host, port=self.port, error=str(e)
            )
            raise

    def _sync_connect(self):
        """Synchronous connection helper"""
        connections.connect(
            alias=self.connection_alias,
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
        )

        # Create collection if it doesn't exist
        if not utility.has_collection(
            self.collection_name, using=self.connection_alias
        ):
            self._create_collection()

        # Get collection reference
        self._collection = Collection(
            name=self.collection_name, using=self.connection_alias
        )

        # Load collection into memory
        self._collection.load()

    def _create_collection(self):
        """Create Milvus collection with proper schema"""
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(
                name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension
            ),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="label", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="severity", dtype=DataType.VARCHAR, max_length=20),
            FieldSchema(name="confidence", dtype=DataType.FLOAT),
        ]

        schema = CollectionSchema(
            fields=fields, description="Prompt injection detection embeddings"
        )

        collection = Collection(
            name=self.collection_name, schema=schema, using=self.connection_alias
        )

        # Create index for vector search
        index_param = {
            "index_type": self.index_type,
            "metric_type": self.metric_type,
            "params": {"nlist": 1024},  # IVF_FLAT parameter
        }

        collection.create_index(field_name="embedding", index_params=index_param)

        logger.info(
            "milvus_collection_created",
            collection=self.collection_name,
            index_type=self.index_type,
        )

    @with_error_handling
    @with_logging
    async def search(
        self, embedding: List[float], limit: int = 5
    ) -> List[SearchResult]:
        """Search for similar embeddings (legacy method)"""
        return await self.similarity_search(embedding, threshold=0.0, k=limit)

    @with_error_handling
    @with_logging
    async def similarity_search(
        self, embedding: List[float], threshold: float = 0.75, k: int = 5
    ) -> List[SearchResult]:
        """Search for embeddings above similarity threshold"""
        await self._connect()

        try:
            # Run search in thread pool
            results = await asyncio.get_event_loop().run_in_executor(
                None, self._sync_search, embedding, threshold, k
            )

            logger.info(
                "milvus_search_completed",
                results_count=len(results),
                threshold=threshold,
            )

            return results

        except Exception as e:
            logger.error("milvus_search_failed", error=str(e))
            raise

    def _sync_search(
        self, embedding: List[float], threshold: float, k: int
    ) -> List[SearchResult]:
        """Synchronous search helper"""
        search_params = {"metric_type": self.metric_type, "params": {"nprobe": 10}}

        # Perform vector search
        search_results = self._collection.search(
            data=[embedding],
            anns_field="embedding",
            param=search_params,
            limit=k * 2,  # Get more results to filter by threshold
            output_fields=["text", "label", "category", "severity", "confidence"],
        )

        results = []
        for hits in search_results:
            for hit in hits:
                # Convert distance to similarity score
                # For COSINE metric, distance = 1 - cosine_similarity
                similarity = 1.0 - hit.distance

                if similarity >= threshold:
                    metadata = {
                        "label": hit.entity.get("label", "unknown"),
                        "category": hit.entity.get("category", "unknown"),
                        "severity": hit.entity.get("severity", "medium"),
                        "confidence": hit.entity.get("confidence", 0.0),
                        "id": hit.id,
                    }

                    results.append(
                        SearchResult(
                            similarity=similarity,
                            text=hit.entity.get("text", ""),
                            metadata=metadata,
                        )
                    )

        # Sort by similarity descending and limit
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:k]

    @with_error_handling
    @with_logging
    async def add(
        self, embedding: List[float], text: str, metadata: dict = None
    ) -> str:
        """Add embedding to database"""
        await self._connect()

        if metadata is None:
            metadata = {}

        try:
            # Run insert in thread pool
            entity_id = await asyncio.get_event_loop().run_in_executor(
                None, self._sync_add, embedding, text, metadata
            )

            logger.info(
                "milvus_embedding_added", entity_id=entity_id, text_preview=text[:50]
            )

            return str(entity_id)

        except Exception as e:
            logger.error("milvus_add_failed", error=str(e))
            raise

    def _sync_add(self, embedding: List[float], text: str, metadata: dict) -> int:
        """Synchronous add helper"""
        entities = [
            [embedding],  # embedding field
            [text[:4096]],  # text field (truncate to max length)
            [metadata.get("label", "unknown")],
            [metadata.get("category", "unknown")],
            [metadata.get("severity", "medium")],
            [metadata.get("confidence", 0.0)],
        ]

        insert_result = self._collection.insert(entities)
        self._collection.flush()  # Ensure data is persisted

        return insert_result.primary_keys[0]

    @with_error_handling
    async def health_check(self) -> bool:
        """Check if database is healthy"""
        try:
            await self._connect()

            # Run health check in thread pool
            is_healthy = await asyncio.get_event_loop().run_in_executor(
                None, self._sync_health_check
            )

            logger.info("milvus_health_check", healthy=is_healthy)
            return is_healthy

        except Exception as e:
            logger.error("milvus_health_check_failed", error=str(e))
            return False

    def _sync_health_check(self) -> bool:
        """Synchronous health check helper"""
        # Check connection
        if not connections.has_connection(self.connection_alias):
            return False

        # Check collection exists and is loaded
        if not utility.has_collection(
            self.collection_name, using=self.connection_alias
        ):
            return False

        # Check collection stats
        stats = utility.get_query_segment_info(
            self.collection_name, using=self.connection_alias
        )

        return len(stats) >= 0  # Collection accessible

    async def close(self):
        """Close database connection"""
        if self._connected:
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._sync_close)
                self._connected = False
                logger.info("milvus_connection_closed", alias=self.connection_alias)

            except Exception as e:
                logger.error("milvus_close_failed", error=str(e))

    def _sync_close(self):
        """Synchronous close helper"""
        if self._collection:
            self._collection.release()

        if connections.has_connection(self.connection_alias):
            connections.disconnect(self.connection_alias)

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        await self._connect()

        try:
            stats = await asyncio.get_event_loop().run_in_executor(
                None, self._sync_get_stats
            )
            return stats

        except Exception as e:
            logger.error("milvus_stats_failed", error=str(e))
            return {}

    def _sync_get_stats(self) -> Dict[str, Any]:
        """Get collection statistics synchronously"""
        stats = utility.get_query_segment_info(
            self.collection_name, using=self.connection_alias
        )

        total_entities = sum(stat.num_rows for stat in stats)

        return {
            "collection_name": self.collection_name,
            "total_entities": total_entities,
            "segments": len(stats),
            "index_type": self.index_type,
            "metric_type": self.metric_type,
            "dimension": self.dimension,
        }
