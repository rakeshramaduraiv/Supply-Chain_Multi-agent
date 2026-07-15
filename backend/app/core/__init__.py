"""
AMASCI Core Module
==================
Cross-cutting concerns: configuration, security, constants, enums.
"""

from app.core.config import get_settings

settings = get_settings()
