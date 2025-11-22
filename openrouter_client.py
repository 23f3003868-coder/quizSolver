# openrouter_client.py
import httpx
import logging
from settings import OPENROUTER_API_KEY, OPENROUTER_MODEL

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    # Optional but recommended by OpenRouter:
    "HTTP-Referer": "https://quizsolver-0cy6.onrender.com",  # using your service URL
    "X-Title": "TDS LLM Quiz Solver",
}

async def call_llm(system_prompt: str, user_prompt: str, *, temperature: float = 0.0, model: str | None = None) -> str:
    logger.info(f"Calling LLM with model: {model or OPENROUTER_MODEL}, system prompt length: {len(system_prompt)}, user prompt length: {len(user_prompt)}")

    # Log only the first 100 characters of prompts to avoid logging sensitive data
    logger.debug(f"System prompt preview: {system_prompt[:100]}...")
    logger.debug(f"User prompt preview: {user_prompt[:100]}...")

    payload = {
        "model": model or OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            logger.debug("Making request to OpenRouter API")
            resp = await client.post(OPENROUTER_URL, headers=HEADERS, json=payload)
            logger.debug(f"Response status: {resp.status_code}")

            resp.raise_for_status()
            data = resp.json()

            # Check if the response contains an error
            if "error" in data:
                error_msg = data["error"].get("message", "Unknown error from OpenRouter API")
                logger.error(f"OpenRouter API returned error: {error_msg}")
                raise Exception(f"OpenRouter API error: {error_msg}")

            # Extract the content from the response
            if "choices" in data and len(data["choices"]) > 0:
                response_content = data["choices"][0]["message"]["content"]
                logger.info(f"Received response from LLM, content length: {len(response_content)}")
                logger.debug(f"Response preview: {response_content[:100]}...")

                return response_content
            else:
                logger.error(f"No choices found in response. Response: {data}")
                raise Exception("Invalid response format from OpenRouter API - no choices available")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from OpenRouter API: {e.response.status_code} - {e}")
        logger.error(f"Response content: {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Error calling LLM: {e}", exc_info=True)
        raise