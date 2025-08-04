"""
Stage 2: Vector similarity with clean abstractions
"""

from typing import List, Dict, Any, Optional
import structlog
import asyncio

from ..core.scanner import ScanContext, Stage, early_exit, log_stage

logger = structlog.get_logger(__name__)

# Optional import - graceful degradation
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    SentenceTransformer = None

logger = structlog.get_logger(__name__)


def embedding_cache(model_name: str):
    """Decorator for caching embeddings - abstracts caching complexity"""
    _cache = {}
    _model = None
    
    def decorator(func):
        async def wrapper(self, text: str) -> List[float]:
            nonlocal _model, _cache
            
            if not HAS_SENTENCE_TRANSFORMERS:
                logger.warning("sentence_transformers_not_available")
                return [0.0] * 384  # Return dummy embedding
            
            # Initialize model once (lazy loading)
            if _model is None:
                _model = SentenceTransformer(model_name)
            
            # Check cache first
            if text in _cache:
                return _cache[text]
            
            # Generate and cache embedding
            embedding = await func(self, text, _model)
            _cache[text] = embedding
            return embedding
        return wrapper
    return decorator


def similarity_threshold(threshold: float):
    """Decorator for similarity threshold checking"""
    def decorator(func):
        async def wrapper(self, context: ScanContext, similarity_score: float) -> ScanContext:
            is_match = similarity_score >= threshold
            return await func(self, context, similarity_score, is_match)
        return wrapper
    return decorator


class VectorStage:
    """
    Stage 2: Vector similarity analysis
    Clean abstractions for embedding and similarity operations
    """
    
    def __init__(self, vector_db_client=None):
        # YAGNI: Simple initialization, inject dependencies
        self.vector_db = vector_db_client
    
    @embedding_cache("all-MiniLM-L6-v2")  # Abstract embedding complexity
    async def _get_embedding(self, text: str, model=None) -> List[float]:
        """Generate embedding - complexity abstracted by decorator"""
        if model is None:
            return [0.0] * 384  # Fallback
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(None, lambda: model.encode(text))
        return embedding.tolist()
    
    async def _find_similar_attacks(self, embedding: List[float]) -> float:
        """
        Simple similarity search - KISS principle
        Returns highest similarity score found
        """
        if not self.vector_db:
            return 0.0  # Graceful degradation - YAGNI
        
        try:
            # Simple search - let vector DB handle complexity
            results = await self.vector_db.search(embedding, limit=1)
            return results[0].similarity if results else 0.0
        except Exception as e:
            logger.warning("vector_search_failed", error=str(e))
            return 0.0
    
    @log_stage("vector")
    @early_exit(threshold=80)  # Exit early if vector match is strong
    @similarity_threshold(0.85)  # Abstract threshold logic
    async def process(self, context: ScanContext, similarity_score: float, is_match: bool) -> ScanContext:
        """
        Simple processing - decorators handled the complexity
        """
        # Get embedding for the prompt
        embedding = await self._get_embedding(context.prompt)
        
        # Find similar known attacks
        similarity_score = await self._find_similar_attacks(embedding)
        
        # Calculate risk based on similarity
        if is_match:
            risk_points = int(similarity_score * 40)  # Scale to 0-40 points
            context.flags.append("VECTOR_MATCH")
        else:
            risk_points = int(similarity_score * 20)  # Lower risk for weak matches
        
        context.risk_score += risk_points
        context.stage_scores["vector"] = risk_points
        context.confidence = max(context.confidence, similarity_score)
        
        logger.info(
            "vector_results",
            similarity_score=similarity_score,
            is_match=is_match,
            risk_points=risk_points,
            request_id=context.request_id
        )
        
        return context