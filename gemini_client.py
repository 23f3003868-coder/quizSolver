# gemini_client.py
import logging
import asyncio
import google.generativeai as genai
from settings import GOOGLE_API_KEY

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)

async def call_gemini(system_prompt: str, user_prompt: str, *, temperature: float = 0.0, model: str = "gemini-pro") -> str:
    """
    Call Google Gemini API with system and user prompts.
    
    Args:
        system_prompt: System instruction prompt
        user_prompt: User query prompt
        temperature: Sampling temperature (default 0.0 for deterministic)
        model: Model name (default "gemini-pro")
        
    Returns:
        Response text from Gemini
    """
    logger.info(f"Calling Gemini API with model: {model}")
    logger.debug(f"System prompt preview: {system_prompt[:100]}...")
    logger.debug(f"User prompt preview: {user_prompt[:100]}...")
    
    try:
        # Combine system and user prompts for Gemini (Gemini doesn't have separate system messages)
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # Create model instance
        model_instance = genai.GenerativeModel(model)
        
        # Run synchronous call in executor to make it async
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model_instance.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                )
            )
        )
        
        result_text = response.text
        logger.info(f"Received response from Gemini, content length: {len(result_text)}")
        logger.debug(f"Full Gemini response: {result_text}")
        
        return result_text
        
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}", exc_info=True)
        raise

