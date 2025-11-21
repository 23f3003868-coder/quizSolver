# settings.py
import os
import logging

logger = logging.getLogger(__name__)

QUIZ_SECRET = os.getenv("QUIZ_SECRET", "")
QUIZ_EMAIL = os.getenv("QUIZ_EMAIL", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "huggingface/unsloth/mistral-nemo-instruct-2407")  # Alternative free model

# Safety: assert presence in runtime, but don't crash on import
def validate_settings():
    logger.info("Validating settings...")
    if not QUIZ_SECRET:
        logger.error("QUIZ_SECRET not set")
        raise RuntimeError("QUIZ_SECRET not set")
    else:
        logger.info("QUIZ_SECRET is set")

    if not QUIZ_EMAIL:
        logger.error("QUIZ_EMAIL not set")
        raise RuntimeError("QUIZ_EMAIL not set")
    else:
        logger.info("QUIZ_EMAIL is set")

    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not set")
        raise RuntimeError("OPENROUTER_API_KEY not set")
    else:
        logger.info("OPENROUTER_API_KEY is set")

    logger.info(f"Settings validated successfully. Model: {OPENROUTER_MODEL}")