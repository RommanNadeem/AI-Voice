"""
Core utilities and shared components for Companion Agent
"""

from .config import *
from .validators import *

__all__ = [
    'Config',
    'is_valid_uuid',
    'extract_uuid_from_identity',
    'can_write_for_current_user',
]

