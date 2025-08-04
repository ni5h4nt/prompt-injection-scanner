"""
Core scanner pipeline with decorator-driven stage orchestration.
Follows KISS and YAGNI principles with clean abstractions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol, Optional, Dict, Any
from functools import wraps
import asyncio
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ScanResult:
    """Simple result container - KISS principle"""
    risk_score: int
    confidence: float
    flags: list[str]
    stage_scores: Dict[str, int]
    request_id: str


@dataclass  
class ScanContext:
    """Context passed through pipeline - contains everything needed"""
    prompt: str
    request_id: str
    metadata: Dict[str, Any]
    risk_score: int = 0
    confidence: float = 0.0
    flags: list[str] = None
    stage_scores: Dict[str, int] = None
    should_exit_early: bool = False
    
    def __post_init__(self):
        if self.flags is None:
            self.flags = []
        if self.stage_scores is None:
            self.stage_scores = {}


class Stage(Protocol):
    """Simple stage protocol - YAGNI: only what we need"""
    
    async def process(self, context: ScanContext) -> ScanContext:
        """Process context and return updated context"""
        ...


def early_exit(threshold: int):
    """Decorator for early exit logic - abstracts complexity away"""
    def decorator(stage_func):
        @wraps(stage_func)
        async def wrapper(self, context: ScanContext) -> ScanContext:
            # Run the stage
            context = await stage_func(self, context)
            
            # Check early exit condition
            if context.risk_score >= threshold:
                context.should_exit_early = True
                logger.info(
                    "early_exit_triggered",
                    stage=stage_func.__name__,
                    risk_score=context.risk_score,
                    threshold=threshold
                )
            
            return context
        return wrapper
    return decorator


def log_stage(stage_name: str):
    """Decorator for stage logging - abstracts boilerplate"""
    def decorator(stage_func):
        @wraps(stage_func)
        async def wrapper(self, context: ScanContext) -> ScanContext:
            logger.debug("stage_started", stage=stage_name, request_id=context.request_id)
            
            try:
                context = await stage_func(self, context)
                logger.info(
                    "stage_completed",
                    stage=stage_name,
                    risk_score=context.risk_score,
                    request_id=context.request_id
                )
                return context
            except Exception as e:
                logger.error(
                    "stage_failed",
                    stage=stage_name,
                    error=str(e),
                    request_id=context.request_id
                )
                raise
        return wrapper
    return decorator


class Scanner:
    """
    Main scanner class - Simple pipeline orchestration
    Uses Strategy pattern for pluggable stages
    """
    
    def __init__(self, 
                 heuristic_stage: Stage,
                 vector_stage: Stage, 
                 guardian_stage: Stage):
        self.stages = [
            ("heuristic", heuristic_stage),
            ("vector", vector_stage),
            ("guardian", guardian_stage)
        ]
    
    async def scan(self, prompt: str, request_id: str = None, metadata: Dict[str, Any] = None) -> ScanResult:
        """
        Simple scan method - KISS principle
        Pipeline runs stages in sequence with early exit
        """
        from uuid import uuid4
        
        context = ScanContext(
            prompt=prompt,
            request_id=request_id or str(uuid4()),
            metadata=metadata or {}
        )
        
        # Run pipeline stages
        for stage_name, stage in self.stages:
            context = await stage.process(context)
            
            # Early exit if risk is high enough
            if context.should_exit_early:
                logger.info("pipeline_early_exit", stage=stage_name, request_id=context.request_id)
                break
        
        return ScanResult(
            risk_score=context.risk_score,
            confidence=context.confidence,
            flags=context.flags,
            stage_scores=context.stage_scores,
            request_id=context.request_id
        )