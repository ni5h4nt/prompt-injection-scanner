"""Vector similarity stage - uses embeddings to detect semantic similarities
Complete implementation with sentence transformers and vector database
"""

import asyncio
from typing import Any, Dict, List, Optional

import structlog

from ..core.scanner import (
    ScanContext,
    cache_result,
    early_exit,
    error_handler,
    log_stage,
)
from ..data import get_training_dataset
from ..vector_db.base import VectorDB

logger = structlog.get_logger(__name__)


class VectorStage:
    """Stage 2: Vector similarity search against known attack patterns
    Uses sentence transformers and vector databases for semantic matching
    """

    def __init__(
        self, vector_db: Optional[VectorDB] = None, model_name: str = "all-MiniLM-L6-v2"
    ):
        super().__init__()
        self.vector_db = vector_db
        self.model_name = model_name
        self.similarity_threshold = 0.75
        self.name = "vector"
        self._model = None
        self._model_lock = asyncio.Lock()

    async def _initialize_model(self):
        """Initialize sentence transformer model lazily"""
        if self._model is None:
            async with self._model_lock:
                if self._model is None:  # Double-check pattern
                    try:
                        from sentence_transformers import SentenceTransformer

                        self._model = SentenceTransformer(self.model_name)
                        logger.info(
                            "sentence_transformer_loaded", model=self.model_name
                        )
                    except ImportError:
                        logger.error("sentence_transformers_not_installed")
                        raise ImportError(
                            "sentence-transformers not installed. "
                            "Install with: pip install sentence-transformers"
                        )
                    except Exception as e:
                        logger.error(
                            "model_loading_failed", model=self.model_name, error=str(e)
                        )
                        raise

    @early_exit(threshold=60)
    @log_stage("vector")
    @cache_result(ttl=300)  # Cache for 5 minutes
    @error_handler
    async def process(self, context: ScanContext) -> ScanContext:
        """Process prompt through vector similarity analysis"""
        if not self.vector_db:
            logger.info("vector_db_not_configured_skipping")
            context.flags.append("VECTOR_STAGE_SKIPPED")
            return context

        try:
            # Initialize model if needed
            await self._initialize_model()

            # Get embedding for the prompt
            embedding = await self._get_embedding(context.prompt)

            # Search for similar attack patterns
            similar_attacks = await self.vector_db.similarity_search(
                embedding, threshold=self.similarity_threshold, k=5
            )

            if similar_attacks:
                # Calculate risk based on similarity scores and categories
                risk_score = self._calculate_risk_score(similar_attacks)

                context.risk_score += risk_score
                context.flags.append("VECTOR_SIMILARITY_MATCH")

                # Determine threat types from matches
                threat_types = set()
                for attack in similar_attacks:
                    category = attack.metadata.get("category", "unknown")
                    if category != "benign":
                        threat_types.add(category)

                if threat_types:
                    context.add_metadata("threat_types", list(threat_types))

                # Add details about matches
                context.add_metadata(
                    "similar_attacks",
                    [
                        {
                            "text_preview": attack.text[:100] + "...",
                            "similarity": round(attack.similarity, 3),
                            "category": attack.metadata.get("category", "unknown"),
                            "severity": attack.metadata.get("severity", "medium"),
                        }
                        for attack in similar_attacks
                    ],
                )

                max_similarity = max(attack.similarity for attack in similar_attacks)
                logger.info(
                    "vector_similarity_found",
                    count=len(similar_attacks),
                    max_similarity=round(max_similarity, 3),
                    risk_score=risk_score,
                    threat_types=list(threat_types),
                )
            else:
                context.risk_score += 5  # Low baseline risk
                logger.debug("no_vector_similarities_found")

        except Exception as e:
            logger.error("vector_stage_error", error=str(e))
            context.flags.append("VECTOR_STAGE_ERROR")
            context.risk_score += 10  # Small penalty for errors

        return context

    def _calculate_risk_score(self, similar_attacks: List[Any]) -> int:
        """Calculate risk score based on similarity matches"""
        if not similar_attacks:
            return 5

        # Get the highest similarity score
        max_similarity = max(attack.similarity for attack in similar_attacks)

        # Weight by severity of matched attacks
        severity_weights = {"critical": 1.2, "high": 1.0, "medium": 0.8, "low": 0.6}

        weighted_scores = []
        for attack in similar_attacks:
            severity = attack.metadata.get("severity", "medium")
            weight = severity_weights.get(severity, 0.8)
            weighted_score = attack.similarity * weight
            weighted_scores.append(weighted_score)

        # Use highest weighted score
        max_weighted = max(weighted_scores) if weighted_scores else max_similarity

        # Convert to risk score (0-100)
        risk_score = min(int(max_weighted * 100), 100)

        # Boost risk if multiple high-confidence matches
        high_confidence_matches = [s for s in weighted_scores if s > 0.8]
        if len(high_confidence_matches) > 1:
            risk_score = min(risk_score + 10, 100)

        return max(risk_score, 10)  # Minimum risk score of 10

    async def _get_embedding(self, text: str) -> List[float]:
        """Get vector embedding for text using sentence transformers"""
        if self._model is None:
            await self._initialize_model()

        try:
            # Run embedding generation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(None, self._model.encode, text)
            return embedding.tolist()
        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            # Return zero vector as fallback
            return [0.0] * 384

    async def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings from this model"""
        await self._initialize_model()
        # Most sentence transformer models have known dimensions
        model_dimensions = {
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "all-distilroberta-v1": 768,
            "paraphrase-multilingual-mpnet-base-v2": 768,
        }
        return model_dimensions.get(self.model_name, 384)

    async def embed_training_data(self) -> List[Dict[str, Any]]:
        """Generate embeddings for training dataset"""
        dataset = get_training_dataset()
        embeddings_data = []

        logger.info(
            "generating_embeddings_for_training_data", examples=len(dataset.examples)
        )

        for i, example in enumerate(dataset.examples):
            if i % 50 == 0:  # Log progress every 50 examples
                logger.info(
                    "embedding_progress", completed=i, total=len(dataset.examples)
                )

            embedding = await self._get_embedding(example.text)

            embeddings_data.append(
                {
                    "text": example.text,
                    "embedding": embedding,
                    "metadata": {
                        "label": example.label,
                        "category": example.category.value,
                        "severity": example.severity,
                        "confidence": example.confidence,
                        "source": example.source,
                    },
                }
            )

        logger.info("embedding_generation_complete", total=len(embeddings_data))

        return embeddings_data
