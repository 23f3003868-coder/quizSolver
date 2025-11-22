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
- If the page shows a JSON payload schema, replicate it in answer_json_template, but leave the answer value as null.
- Do NOT include comments or extra fields.
- Output only valid JSON, no explanation text.
"""

async def plan_from_page_text(page_text: str) -> dict:
    logger.info(f"Planning from page text of length {len(page_text)}")
    logger.debug(f"Page text preview: {page_text[:200]}...")

    user_prompt = (
        "Here is the full text content of the quiz page:\n\n"
        f"{page_text}\n\n"
        "Extract the JSON plan as specified. Do not include any markdown formatting, code blocks, or extra text - only return valid JSON."
    )

    try:
        logger.info("Calling LLM for planning")
        raw = await call_llm(PLANNER_SYSTEM_PROMPT, user_prompt)
        logger.info(f"LLM returned raw response of length {len(raw)}")

        logger.debug(f"Raw LLM response: {raw}")

        # Clean up the response to extract JSON if it contains markdown formatting
        cleaned_response = raw.strip()

        # Check if the response is wrapped in markdown code blocks
        if cleaned_response.startswith("```"):
            # Find the first occurrence of ``` and extract content between it and the next ```
            import re
            match = re.search(r'```(?:json)?\s*\n?(.*?)(?:\n?)```', cleaned_response, re.DOTALL)
            if match:
                cleaned_response = match.group(1).strip()
            else:
                # If there's a code block but couldn't extract it properly, log and try to parse as is
                logger.warning("Found markdown block but couldn't extract JSON properly")

        plan = json.loads(cleaned_response)
        logger.info(f"Successfully parsed plan: {plan.get('question_summary', 'N/A')[:50]}...")

        return plan
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response from LLM: {e}")
        logger.error(f"Raw response was: {raw}")
        logger.error(f"Cleaned response was: {cleaned_response}")
        raise
    except Exception as e:
        logger.error(f"Error in planning from page text: {e}", exc_info=True)
        raise