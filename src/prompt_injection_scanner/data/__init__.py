"""
Training data and datasets for the prompt injection scanner
"""

from .training_dataset import (
    PromptInjectionDataset,
    ThreatCategory,
    TrainingExample,
    get_training_dataset,
    training_dataset,
)

__all__ = [
    "PromptInjectionDataset",
    "TrainingExample",
    "ThreatCategory",
    "get_training_dataset",
    "training_dataset",
]
