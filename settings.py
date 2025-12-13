# settings.py
import os
import logging

logger = logging.getLogger(__name__)

# Environment variables - these will be set by the user
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Safety: assert presence in runtime, but don't crash on import
def validate_settings():
    logger.info("Validating settings...")
    
    if not GOOGLE_API_KEY:
        logger.error("GOOGLE_API_KEY not set")
        raise RuntimeError("GOOGLE_API_KEY not set")
    else:
        logger.info("GOOGLE_API_KEY is set")

    logger.info("Settings validated successfully")