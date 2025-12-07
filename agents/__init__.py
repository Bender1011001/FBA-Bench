"""
Compatibility shim for legacy 'agents' imports.
Redirects to 'src.agents' components.
"""

import sys
from src.agents import multi_domain_controller

# Expose modules that were previously under 'agents'
sys.modules["agents.multi_domain_controller"] = multi_domain_controller

__all__ = ["multi_domain_controller"]