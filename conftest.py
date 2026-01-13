"""Pytest configuration and fixtures.

This module provides shared fixtures and configuration for the test suite.
It enables async test support and provides common test utilities.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"


if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
