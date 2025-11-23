# planner.py
import json
import logging
from openrouter_client import call_llm

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """
You are a planning assistant for solving data quizzes.

You receive the FULL TEXT of a quiz webpage.

Your job is to output a STRICT JSON object with these fields:

{
  "question_summary": "short description of what is being asked",
  "submit_url": "https://...",                     // where to POST the final answer
  "answer_type": "number|string|boolean|json|file",
  "file_urls": ["https://...", "..."],             // any CSV, Excel, PDF, data URLs in the page (if any)
  "answer_json_template": {                        // JSON payload structure to send to submit_url,
    "email": "",                                   // from page instructions
    "secret": "",
    "url": "",
    "answer": null                                 // placeholder
  }
}

Rules:
- If you see relative URLs like "/data/file.csv", resolve them to absolute URLs based on the page's URL
- If the page URL is "https://example.com/quiz" and there's a relative link "/data/file.csv", the absolute URL is "https://example.com/data/file.csv"
- If the page shows a JSON payload schema, replicate it in answer_json_template, but leave the answer value as null.
- Do NOT include comments or extra fields.
- Output only valid JSON, no explanation text.
"""

async def plan_from_page_text(page_text: str, original_url: str = None) -> dict:
    logger.info(f"Planning from page text of length {len(page_text)}, original URL: {original_url}")
    logger.debug(f"Page text preview: {page_text[:200]}...")

    # Build the user prompt with URL context if available
    if original_url:
        # Extract the base URL (origin) from the original URL to help with relative URL resolution
        from urllib.parse import urljoin
        base_url = urljoin(original_url, "/")  # Get the origin part of the URL
        user_prompt = (
            f"Quiz page URL: {original_url}\n\n"
            f"Base URL: {base_url}\n\n"
            "Here is the full text content of the quiz page:\n\n"
            f"{page_text}\n\n"
            f'Important: If the page contains relative URLs like "/data/file.csv", you must convert them to absolute URLs using the base URL ({base_url}).\n'
            f'For example, "/data/file.csv" should become "{base_url}data/file.csv".\n'
            'Do not return placeholder URLs like "https://..." - return the actual resolved URLs.\n\n'
            "Extract the JSON plan as specified. Do not include any markdown formatting, code blocks, or extra text - only return valid JSON."
        )
    else:
        user_prompt = (
            "Here is the full text content of the quiz page:\n\n"
            f"{page_text}\n\n"
            "Important: If the page contains relative URLs like \"/data/file.csv\", you must convert them to absolute URLs based on the quiz URL that was provided (you won't see the original URL here, but relative links are relative to the origin domain of the quiz page). Do not return placeholder URLs like \"https://...\" - return the actual resolved URLs.\n\n"
            "Extract the JSON plan as specified. Do not include any markdown formatting, code blocks, or extra text - only return valid JSON."
        )

    raw = None
    try:
        logger.info("Calling LLM for planning")
        raw = await call_llm(PLANNER_SYSTEM_PROMPT, user_prompt)
        logger.info(f"LLM returned raw response of length {len(raw)}")

        logger.debug(f"Raw LLM response: {raw}")

        # Clean up the response to extract JSON if it contains markdown formatting
        cleaned_response = raw.strip()

        # Handle model-specific token prefixes (e.g., <s> [OUT] from Mistral models)
        if cleaned_response.startswith("<s>"):
            # Remove common token prefixes from models
            cleaned_response = cleaned_response.split("[OUT]", 1)[-1].strip()
            # Sometimes there are trailing tags like [/OUT] that need to be removed
            if "[/OUT]" in cleaned_response:
                cleaned_response = cleaned_response.split("[/OUT]")[0].strip()
        elif cleaned_response.startswith("```"):
            # Find the first occurrence of ``` and extract content between it and the next ```
            import re
            match = re.search(r'```(?:json)?\s*\n?(.*?)(?:\n?)```', cleaned_response, re.DOTALL)
            if match:
                cleaned_response = match.group(1).strip()
            else:
                # If there's a code block but couldn't extract it properly, log and try to parse as is
                logger.warning("Found markdown block but couldn't extract JSON properly")

        # Try to extract JSON from the cleaned response using regex to handle any remaining formatting
        import re
        json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
        if json_match:
            final_json_str = json_match.group(0).strip()
        else:
            # If no JSON object found, try the cleaned_response as is
            final_json_str = cleaned_response

        plan = json.loads(final_json_str)
        logger.info(f"Successfully parsed plan: {plan.get('question_summary', 'N/A')[:50]}...")

        return plan
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response from LLM: {e}")
        logger.error(f"Raw response was: {raw if 'raw' in locals() else 'N/A'}")
        logger.error(f"Cleaned response was: {cleaned_response if 'cleaned_response' in locals() else 'N/A'}")
        logger.error(f"Final JSON string attempted: {final_json_str if 'final_json_str' in locals() else 'N/A'}")
        raise
    except Exception as e:
        logger.error(f"Error in planning from page text: {e}", exc_info=True)
        raise