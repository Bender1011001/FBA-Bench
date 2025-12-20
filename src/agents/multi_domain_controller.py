"""
Multi-Domain Controller for FBA-Bench Agent Architecture.

This module provides the public API for the MultiDomainController, delegating to the coordination subpackage.
"""

from .coordination import MultiDomainController

__all__ = ["MultiDomainController"]
