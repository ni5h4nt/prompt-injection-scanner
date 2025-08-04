"""Stage 1: Heuristic analysis with configurable patterns
"""

from typing import Any, Dict, List

import structlog

from ..core.scanner import ScanContext, early_exit, log_stage
from ..patterns import PatternManager

logger = structlog.get_logger(__name__)


def pattern_matcher_configurable(pattern_manager: PatternManager):
    """Decorator that uses configurable pattern manager"""

    def decorator(func):
        async def wrapper(self, context: ScanContext) -> ScanContext:
            # Use pattern manager to find matches
            matches = pattern_manager.match_patterns(context.prompt)

            # Let the decorated function handle the matches
            return await func(self, context, matches)

        return wrapper

    return decorator


def risk_calculator_dynamic(func):
    """Decorator that calculates risk based on pattern scores"""

    async def wrapper(
        self, context: ScanContext, matches: List[Dict[str, Any]]
    ) -> ScanContext:
        # Calculate risk based on pattern risk scores
        total_risk = sum(match.get("risk_score", 0) for match in matches)

        return await func(self, context, matches, total_risk)

    return wrapper


class HeuristicStage:
    """Stage 1: Fast pattern-based detection with configurable patterns
    Uses PatternManager for flexible, user-defined detection rules
    """

    def __init__(self, pattern_manager: PatternManager = None):
        """Initialize with optional custom pattern manager"""
        self.pattern_manager = pattern_manager or PatternManager()
        logger.info(
            "heuristic_stage_initialized", patterns=len(self.pattern_manager.patterns)
        )

    @log_stage("heuristic")
    @early_exit(threshold=70)  # Exit early if heuristic finds high risk
    async def process(self, context: ScanContext) -> ScanContext:
        """Process with configurable patterns - much more flexible
        KISS: Pattern complexity is abstracted away
        """
        # Use pattern manager to find matches
        matches = self.pattern_manager.match_patterns(context.prompt)

        # Calculate risk based on pattern scores
        risk_points = sum(match.get("risk_score", 0) for match in matches)

        # Extract flags and categories
        flags = [match["pattern_id"] for match in matches]
        categories = list(set(match["category"] for match in matches))

        # Update context
        context.risk_score += risk_points
        context.flags.extend(flags)
        context.stage_scores["heuristic"] = risk_points

        # Calculate confidence based on severity
        high_severity_matches = [
            m for m in matches if m.get("severity") in ["high", "critical"]
        ]
        context.confidence = min(0.9, len(high_severity_matches) * 0.3)

        logger.info(
            "heuristic_results",
            matches_count=len(matches),
            flags=flags,
            categories=categories,
            risk_points=risk_points,
            request_id=context.request_id,
        )

        return context

    def reload_patterns(self) -> None:
        """Reload patterns from configuration"""
        self.pattern_manager.reload_patterns()
        logger.info("patterns_reloaded", patterns=len(self.pattern_manager.patterns))

    def get_pattern_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded patterns"""
        return self.pattern_manager.get_pattern_stats().model_dump()
