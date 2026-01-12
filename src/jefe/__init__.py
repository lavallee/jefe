"""Station Chief - A comprehensive Git repository management system."""

__version__ = "0.1.0"
__author__ = "Station Chief Team"
__email__ = "team@station-chief.dev"

from . import adapters, cli, data, server, web

__all__ = ["adapters", "cli", "data", "server", "web"]
