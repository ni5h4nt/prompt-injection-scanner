"""Feedback loop system for continuous learning from production data
Helps improve detection accuracy over time
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from ..stages.vector import VectorStage
from ..vector_db.base import VectorDB

logger = structlog.get_logger(__name__)


@dataclass
class FeedbackExample:
    """A feedback example from production usage"""

    text: str
    predicted_risk: int
    predicted_label: str
    actual_label: str  # "malicious" or "benign" - human verified
    feedback_type: str  # "false_positive", "false_negative", "correct"
    confidence: float
    timestamp: datetime
    user_id: Optional[str] = None
    source: str = "production"


class FeedbackLoop:
    """Continuous learning system that improves detection based on feedback
    """

    def __init__(self, vector_db: VectorDB, vector_stage: VectorStage):
        self.vector_db = vector_db
        self.vector_stage = vector_stage
        self.feedback_buffer: List[FeedbackExample] = []
        self.buffer_size = 100
        self.learning_threshold = 50  # Min examples before retraining
        self.stats = {
            "total_feedback": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "correct_predictions": 0,
            "last_learning_update": None,
        }

    async def record_feedback(
        self,
        text: str,
        predicted_risk: int,
        predicted_label: str,
        actual_label: str,
        confidence: float = 0.0,
        user_id: Optional[str] = None,
    ):
        """Record feedback from production usage"""
        # Determine feedback type
        if predicted_label == actual_label:
            feedback_type = "correct"
            self.stats["correct_predictions"] += 1
        elif predicted_label == "malicious" and actual_label == "benign":
            feedback_type = "false_positive"
            self.stats["false_positives"] += 1
        elif predicted_label == "benign" and actual_label == "malicious":
            feedback_type = "false_negative"
            self.stats["false_negatives"] += 1
        else:
            feedback_type = "unknown"

        feedback = FeedbackExample(
            text=text,
            predicted_risk=predicted_risk,
            predicted_label=predicted_label,
            actual_label=actual_label,
            feedback_type=feedback_type,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            user_id=user_id,
        )

        self.feedback_buffer.append(feedback)
        self.stats["total_feedback"] += 1

        logger.info(
            "feedback_recorded",
            feedback_type=feedback_type,
            predicted_risk=predicted_risk,
            actual_label=actual_label,
            buffer_size=len(self.feedback_buffer),
        )

        # Trigger learning if buffer is full
        if len(self.feedback_buffer) >= self.buffer_size:
            await self._process_feedback_batch()

    async def record_false_positive(
        self, text: str, predicted_risk: int, confidence: float = 0.0
    ):
        """Convenience method for recording false positives"""
        await self.record_feedback(
            text=text,
            predicted_risk=predicted_risk,
            predicted_label="malicious",
            actual_label="benign",
            confidence=confidence,
        )

    async def record_false_negative(
        self, text: str, predicted_risk: int, confidence: float = 0.0
    ):
        """Convenience method for recording false negatives"""
        await self.record_feedback(
            text=text,
            predicted_risk=predicted_risk,
            predicted_label="benign",
            actual_label="malicious",
            confidence=confidence,
        )

    async def _process_feedback_batch(self):
        """Process accumulated feedback and update the vector database"""
        if len(self.feedback_buffer) < self.learning_threshold:
            logger.debug(
                "insufficient_feedback_for_learning",
                current=len(self.feedback_buffer),
                required=self.learning_threshold,
            )
            return

        logger.info("processing_feedback_batch", batch_size=len(self.feedback_buffer))

        try:
            # Separate feedback by type
            false_positives = [
                f for f in self.feedback_buffer if f.feedback_type == "false_positive"
            ]
            false_negatives = [
                f for f in self.feedback_buffer if f.feedback_type == "false_negative"
            ]

            # Process false negatives (add as malicious examples)
            if false_negatives:
                await self._add_malicious_examples(false_negatives)

            # Process false positives (add as benign examples or adjust thresholds)
            if false_positives:
                await self._add_benign_examples(false_positives)

            # Update statistics
            self.stats["last_learning_update"] = datetime.utcnow()

            # Clear the buffer
            processed_count = len(self.feedback_buffer)
            self.feedback_buffer.clear()

            logger.info(
                "feedback_batch_processed",
                processed=processed_count,
                false_positives=len(false_positives),
                false_negatives=len(false_negatives),
            )

        except Exception as e:
            logger.error("feedback_processing_failed", error=str(e))

    async def _add_malicious_examples(self, false_negatives: List[FeedbackExample]):
        """Add false negative examples as new malicious training data"""
        for feedback in false_negatives:
            try:
                # Generate embedding for the missed attack
                embedding = await self.vector_stage._get_embedding(feedback.text)

                # Add to vector database as malicious
                await self.vector_db.add(
                    embedding=embedding,
                    text=feedback.text,
                    metadata={
                        "label": "malicious",
                        "category": "feedback_learned",
                        "severity": "medium",  # Conservative severity for learned examples
                        "confidence": feedback.confidence,
                        "source": "feedback_loop",
                        "original_risk": feedback.predicted_risk,
                        "learned_at": feedback.timestamp.isoformat(),
                    },
                )

                logger.info(
                    "malicious_example_added_from_feedback",
                    text_preview=feedback.text[:50] + "...",
                    original_risk=feedback.predicted_risk,
                )

            except Exception as e:
                logger.error(
                    "failed_to_add_malicious_example",
                    text=feedback.text[:50],
                    error=str(e),
                )

    async def _add_benign_examples(self, false_positives: List[FeedbackExample]):
        """Add false positive examples as benign training data"""
        for feedback in false_positives:
            try:
                # Generate embedding for the incorrectly flagged benign text
                embedding = await self.vector_stage._get_embedding(feedback.text)

                # Add to vector database as benign
                await self.vector_db.add(
                    embedding=embedding,
                    text=feedback.text,
                    metadata={
                        "label": "benign",
                        "category": "benign",
                        "severity": "low",
                        "confidence": feedback.confidence,
                        "source": "feedback_loop",
                        "original_risk": feedback.predicted_risk,
                        "learned_at": feedback.timestamp.isoformat(),
                    },
                )

                logger.info(
                    "benign_example_added_from_feedback",
                    text_preview=feedback.text[:50] + "...",
                    original_risk=feedback.predicted_risk,
                )

            except Exception as e:
                logger.error(
                    "failed_to_add_benign_example",
                    text=feedback.text[:50],
                    error=str(e),
                )

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from feedback data"""
        total = self.stats["total_feedback"]
        if total == 0:
            return {
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
                "total_feedback": 0,
            }

        correct = self.stats["correct_predictions"]
        fp = self.stats["false_positives"]
        fn = self.stats["false_negatives"]
        tp = correct - fp  # True positives (assuming some correct were malicious)

        accuracy = correct / total if total > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return {
            "accuracy": round(accuracy, 3),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1_score, 3),
            "total_feedback": total,
            "correct_predictions": correct,
            "false_positives": fp,
            "false_negatives": fn,
            "last_learning_update": self.stats["last_learning_update"],
        }

    async def suggest_threshold_adjustments(self) -> Dict[str, Any]:
        """Suggest threshold adjustments based on feedback patterns"""
        metrics = await self.get_performance_metrics()
        suggestions = []

        # High false positive rate - suggest increasing threshold
        if metrics["false_positives"] > metrics["false_negatives"] * 2:
            suggestions.append(
                {
                    "type": "increase_threshold",
                    "reason": "High false positive rate detected",
                    "suggested_change": "+0.05",
                    "confidence": 0.8,
                }
            )

        # High false negative rate - suggest decreasing threshold
        elif metrics["false_negatives"] > metrics["false_positives"] * 2:
            suggestions.append(
                {
                    "type": "decrease_threshold",
                    "reason": "High false negative rate detected",
                    "suggested_change": "-0.05",
                    "confidence": 0.8,
                }
            )

        # Balanced performance - no changes needed
        else:
            suggestions.append(
                {
                    "type": "no_change",
                    "reason": "Performance appears balanced",
                    "suggested_change": "0.0",
                    "confidence": 0.9,
                }
            )

        return {
            "suggestions": suggestions,
            "current_metrics": metrics,
            "sample_size": metrics["total_feedback"],
        }

    async def export_feedback_data(self) -> List[Dict[str, Any]]:
        """Export feedback data for external analysis"""
        return [asdict(feedback) for feedback in self.feedback_buffer]

    async def force_learning_update(self):
        """Force processing of feedback buffer regardless of size"""
        if self.feedback_buffer:
            logger.info(
                "forcing_learning_update", buffer_size=len(self.feedback_buffer)
            )
            await self._process_feedback_batch()
        else:
            logger.info("no_feedback_to_process")


# Global feedback loop instance
_feedback_loop: Optional[FeedbackLoop] = None


def initialize_feedback_loop(
    vector_db: VectorDB, vector_stage: VectorStage
) -> FeedbackLoop:
    """Initialize global feedback loop instance"""
    global _feedback_loop
    _feedback_loop = FeedbackLoop(vector_db, vector_stage)
    logger.info("feedback_loop_initialized")
    return _feedback_loop


def get_feedback_loop() -> Optional[FeedbackLoop]:
    """Get global feedback loop instance"""
    return _feedback_loop
