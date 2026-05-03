"""Synthetic source data generation for Package 1."""

from account_health.synthetic.generator import generate_synthetic_source_data
from account_health.synthetic.schemas import (
    ALLOWED_VALUES,
    FOREIGN_KEYS,
    PRIMARY_KEYS,
    REQUIRED_COLUMNS,
    SOURCE_TABLES,
)

__all__ = [
    "ALLOWED_VALUES",
    "FOREIGN_KEYS",
    "PRIMARY_KEYS",
    "REQUIRED_COLUMNS",
    "SOURCE_TABLES",
    "generate_synthetic_source_data",
]
