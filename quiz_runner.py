# quiz_runner.py
import time
from typing import Any, Dict
import asyncio
import httpx
import logging
from browser_utils import fetch_quiz_page
from planner import plan_from_page_text
from data_utils import download_files, load_dataframes
from openrouter_client import call_llm
import json
import types
import numpy as np
import pandas as pd


# Configure logging
logger = logging.getLogger(__name__)

PYTHON_SOLVER_SYSTEM = """
You are a Python data analysis assistant.

You will be given:
- A description of the question
- The full text of the quiz page
- A description of loaded data files

You must output ONLY a JSON object:

{
  "explanation": "short natural language explanation of what you will do",
  "code": "def solve(data, page_text):\\n    ...\\n    return answer"
}

Rules:
- The function `solve(data, page_text)` receives:
  - data: dict from URL string to python object:
    * CSV/Excel → pandas.DataFrame
    * PDF      → dict with 'texts' (list[str]) and 'tables' (nested lists)
    * For API responses: the JSON response directly
    * Additional context may be available in data['email'], data['secret'], data['current_url'] if needed
  - page_text: full text of the quiz page.
- If the quiz requires authentication credentials or specific URLs, check data dictionary for 'email', 'secret', 'current_url' keys
- Use only numpy and pandas operations; they are already imported as `import numpy as np` and `import pandas as pd`.
- Do not import or use requests, urllib, or any network modules; data is already loaded.
- No external network calls.
- Do not print or use any input/output functions like print(), input().
- Return the final `answer` in a type consistent with the question (number/string/boolean/json-serializable).
- Code MUST be valid Python 3.
"""


async def make_solver_code(question_summary: str, page_text: str, data_descr: str) -> str:
    logger.info(f"Generating solver code for question: {question_summary[:50]}...")
    user_prompt = f"""
Question summary:
{question_summary}

Quiz page text:
{page_text}

Data description:
{data_descr}

Produce JSON with 'explanation' and 'code' fields as specified. Do not include any markdown formatting, code blocks, or extra text - only return valid JSON.
"""
    raw = None
    try:
        raw = await call_llm(PYTHON_SOLVER_SYSTEM, user_prompt)

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
            import re
            match = re.search(r'```(?:json)?\s*\n?(.*?)(?:\n?)```', cleaned_response, re.DOTALL)
            if match:
                cleaned_response = match.group(1).strip()
            else:
                logger.warning("Found markdown block in solver code response but couldn't extract JSON properly")

        # Try to extract JSON from the cleaned response using regex to handle any remaining formatting
        import re
        json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
        if json_match:
            final_json_str = json_match.group(0).strip()
        else:
            # If no JSON object found, try the cleaned_response as is
            final_json_str = cleaned_response

        obj = json.loads(final_json_str)
        code = obj["code"]

        # Validate the generated code doesn't contain restricted imports
        if 'import requests' in code or 'import urllib' in code or '.get(' in code or '.post(' in code:
            logger.error(f"Generated code contains restricted network operations: {code}")
            raise ValueError("Generated code contains restricted network operations")

        logger.info("Successfully generated and validated solver code")
        return code
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response from LLM: {e}")
        logger.error(f"Raw solver code response: {raw if 'raw' in locals() else 'N/A'}")
        logger.error(f"Cleaned solver code response: {cleaned_response if 'cleaned_response' in locals() else 'N/A'}")
        logger.error(f"Final JSON string attempted: {final_json_str if 'final_json_str' in locals() else 'N/A'}")
        raise
    except Exception as e:
        logger.error(f"Error generating solver code: {e}")
        logger.debug(f"Raw solver code response: {raw if 'raw' in locals() else 'N/A'}")
        logger.debug(f"Cleaned solver code response: {cleaned_response if 'cleaned_response' in locals() else 'N/A'}")
        raise


def describe_data_structures(data: Dict[str, Any]) -> str:
    """
    Produce a short text description of the loaded data for the LLM:
    - For DataFrames: show shape and column names.
    - For PDFs: number of pages and number of tables.
    - For API JSON responses: show keys and basic structure.
    """
    logger.info(f"Describing data structures for {len(data)} data sources")
    lines = []
    for url, obj in data.items():
        if url in ['email', 'secret', 'current_url']:
            # Handle special authentication context keys
            logger.info(f"  {url}: Authentication context (available for use in code)")
            lines.append(f"{url}: Authentication credential/context information available for use in solver code")
        elif hasattr(obj, "head"):  # assume DataFrame-like
            cols = list(obj.columns)
            logger.info(f"  {url}: DataFrame shape={obj.shape}, columns={cols}")
            lines.append(f"{url} (key in data dict): DataFrame shape={obj.shape}, columns={cols}")
        elif isinstance(obj, dict) and "texts" in obj and "tables" in obj:
            num_pages = len(obj["texts"])
            logger.info(f"  {url}: PDF with {num_pages} pages")
            lines.append(f"{url} (key in data dict): PDF with {num_pages} pages")
        elif isinstance(obj, dict):
            # This is likely API JSON data - describe its structure
            keys = list(obj.keys()) if isinstance(obj, dict) and not (obj.get("texts") and obj.get("tables")) else "complex_object"
            if isinstance(keys, list):
                logger.info(f"  {url}: JSON API response with keys={keys}")
                lines.append(f"{url} (key in data dict): JSON API response with keys={keys}")
            else:
                logger.info(f"  {url}: JSON API response, type={type(obj)}, sample_keys={list(obj.keys())[:5] if hasattr(obj, 'keys') else 'N/A'}")
                lines.append(f"{url} (key in data dict): JSON API response, type={type(obj)}, sample_keys={list(obj.keys())[:5] if hasattr(obj, 'keys') else 'N/A'}")
        elif isinstance(obj, list):
            logger.info(f"  {url}: JSON API response list with {len(obj)} items")
            lines.append(f"{url} (key in data dict): JSON API response list with {len(obj)} items")
        else:
            logger.info(f"  {url}: Unrecognized object of type {type(obj)}")
            lines.append(f"{url} (key in data dict): Unrecognized object of type {type(obj)}")
    result = "\n".join(lines)
    logger.debug(f"Data description: {result}")
    return result


def run_solver_code(code: str, context_data: Dict[str, Any]) -> Any:
    """
    Execute the LLM-generated code defining solve(data, page_text)
    and return the answer.
    """
    logger.info("Executing solver code")
    logger.debug(f"Code to execute: {code[:200]}...")

    # Extract the original data and context
    quiz_data = context_data.get("quiz_data", {})
    page_text = context_data.get("page_text", "")
    email = context_data.get("email", "")
    secret = context_data.get("secret", "")
    current_url = context_data.get("current_url", "")

    # Restricted globals - only allow safe operations, no network access
    global_env = {
        "__builtins__": __builtins__,
        "pd": pd,
        "np": np,
    }
    local_env: dict = {}
    try:
        exec(code, global_env, local_env)
        solve_fn = local_env.get("solve")
        if not isinstance(solve_fn, types.FunctionType):
            logger.error("No solve(data, page_text) function found in generated code")
            raise RuntimeError("No solve(data, page_text) function found")

        logger.info("Calling solve function with provided data")
        # Pass the quiz data and page text to the original function signature
        # If the code expects the new context, we need to handle it differently
        # First try the original signature
        try:
            result = solve_fn(quiz_data, page_text)
        except TypeError:
            # If that fails, try with the full context (in case LLM used more advanced approach)
            try:
                result = solve_fn(quiz_data, page_text, email, secret, current_url)
            except TypeError:
                # If that also fails, try with a context dict
                result = solve_fn(context_data)

        logger.info(f"Solver function returned result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error executing solver code: {e}")
        raise


async def solve_single_quiz(url: str, email: str, secret: str, deadline: float) -> dict:
    """
    Solve a single quiz and return the result.
    """
    logger.info(f"Starting to solve single quiz: {url}")

    if time.time() >= deadline:
        logger.warning("Deadline exceeded before starting quiz")
        return {"correct": False, "reason": "Deadline exceeded before starting"}

    # Fetch the quiz page
    logger.info("Fetching quiz page")
    try:
        html, page_text = await fetch_quiz_page(url)
        logger.info(f"Successfully fetched quiz page, HTML length: {len(html)}, text length: {len(page_text)}")
    except Exception as e:
        logger.error(f"Error fetching quiz page: {e}")
        raise

    # Plan the solution
    logger.info("Planning solution from page HTML and text")
    try:
        # Use the full HTML content to help identify links and data files, but pass both HTML and text
        plan = await plan_from_page_text(html, url)
        logger.info(f"Successfully created plan: {plan.get('question_summary', 'N/A')[:50]}...")
    except Exception as e:
        logger.error(f"Error planning from page content: {e}")
        raise

    submit_url = plan.get("submit_url")
    file_urls = plan.get("file_urls", [])
    api_urls = plan.get("api_urls", [])  # New field for authenticated API endpoints
    answer_type = plan.get("answer_type")
    answer_json_template = plan.get("answer_json_template", {})

    # Special handling: if the submit URL looks like a quiz page URL rather than a submission endpoint,
    # try using a default submission endpoint instead. Quiz pages typically don't accept POST requests directly.
    original_submit_url = submit_url
    quiz_domains = ['tds-llm-analysis.s-anand.net']  # Add domains that have this pattern
    if (submit_url and
        any(domain in submit_url for domain in quiz_domains) and
        not any(endpoint in submit_url for endpoint in ['/submit', '/api/', '/endpoint'])):
        # This looks like a quiz page, not a submission endpoint.
        # Check if it's a root domain submission case
        if submit_url == "https://tds-llm-analysis.s-anand.net/project2-uv":
            # For project2-uv specifically, submission should go to /submit
            default_submit_url = 'https://tds-llm-analysis.s-anand.net/submit'
            logger.info(f"Detected project2-uv quiz page as submit URL, using /submit endpoint instead: {default_submit_url}")
            submit_url = default_submit_url
        elif '/project2' in submit_url and not submit_url.endswith('/submit'):
            # If it's a project2 related URL but not submit, try /submit
            domain = "https://tds-llm-analysis.s-anand.net"
            default_submit_url = f"{domain}/submit"
            logger.info(f"Detected project2 quiz page as submit URL, using /submit endpoint instead: {default_submit_url}")
            submit_url = default_submit_url

    logger.info(f"Plan details - Submit URL: {submit_url}, File URLs: {len(file_urls)}, API URLs: {len(api_urls)}, Answer type: {answer_type}")

    # Download and load data if needed
    data = {}
    if file_urls:
        logger.info(f"Downloading {len(file_urls)} files")
        try:
            downloaded = await download_files(file_urls)
            logger.info(f"Successfully downloaded files: {list(downloaded.keys())}")
            data = load_dataframes(downloaded)
            logger.info(f"Successfully loaded dataframes: {list(data.keys())}")
        except Exception as e:
            logger.error(f"Error downloading or loading data: {e}")
            raise

    # Download and load data from authenticated API endpoints if needed
    if api_urls:
        logger.info(f"Fetching data from {len(api_urls)} authenticated API endpoints")
        try:
            from data_utils import fetch_api_data
            api_data = await fetch_api_data(api_urls, email, secret, url)
            logger.info(f"Successfully fetched API data: {list(api_data.keys())}")
            # Merge API data with file data using URL as key
            data.update(api_data)
        except Exception as e:
            logger.error(f"Error fetching or loading API data: {e}")
            raise
    else:
        logger.info("No API endpoints to fetch data from")

    # Add auth context to data so LLM can access it if needed
    data['email'] = email
    data['secret'] = secret
    data['current_url'] = url

    # Generate and run solver code
    data_descr = describe_data_structures(data)
    logger.info("Generating solver code")
    try:
        solver_code = await make_solver_code(plan.get("question_summary", ""), page_text, data_descr)
        logger.info("Running solver code")
        # Pass additional context data to the solver code
        context_data = {
            "quiz_data": data,
            "page_text": page_text,
            "email": email,
            "secret": secret,
            "current_url": url
        }
        answer = run_solver_code(solver_code, context_data)  # Pass enriched context data
        logger.info(f"Successfully computed answer: {answer}")
    except Exception as e:
        logger.error(f"Error generating or running solver code: {e}")
        raise

    # Cast answer if needed
    if answer_type == "number":
        logger.info("Casting answer to number")
        try:
            answer = float(answer)
            logger.info(f"Casted answer to float: {answer}")
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not cast answer to float, keeping original: {e}")
            pass  # Keep original answer if conversion fails

    # Build payload
    logger.info("Building submission payload")

    # Use the original quiz page URL (not the submission endpoint) for the 'url' field
    # according to quiz instructions which often say to use the quiz page URL in the payload
    payload = answer_json_template.copy()
    payload.update({
        "email": email,
        "secret": secret,
        "url": url,  # This is the original quiz page URL from the request
        "answer": answer
    })
    logger.info(f"Built payload with keys: {list(payload.keys())}")

    # Submit the answer
    logger.info(f"Submitting answer to {submit_url}")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(submit_url, json=payload)

            # Handle different response types
            if resp.headers.get("content-type", "").startswith("application/json"):
                # If response is JSON, parse it
                result = resp.json()
                logger.info(f"Received JSON submission result: {result}")
                return result
            elif resp.status_code == 405:
                # Handle Method Not Allowed - may need to adjust submission method or URL
                logger.error(f"405 Method Not Allowed when submitting to {submit_url}")
                logger.error(f"Response content: {resp.text}")
                # Try to construct a reasonable result based on status code
                return {
                    "correct": False,
                    "reason": f"Method not allowed when submitting to {submit_url}",
                    "url": None
                }
            else:
                # For non-JSON responses, try to parse or return basic info
                try:
                    # Try to parse as JSON anyway in case it's valid JSON
                    result = resp.json()
                    logger.info(f"Received submission result: {result}")
                    return result
                except:
                    # If can't parse JSON, return status info
                    logger.warning(f"Non-JSON response received: {resp.status_code} - {resp.text}")
                    return {
                        "correct": False,
                        "reason": f"Non-JSON response: {resp.status_code}",
                        "url": None
                    }
    except Exception as e:
        logger.error(f"Error submitting answer: {e}")
        raise


async def run_quiz(url: str, email: str, secret: str, deadline: float):
    """
    Run the quiz chain until completion or timeout.
    """
    logger.info(f"Starting quiz chain: {url}, deadline: {deadline}, time remaining: {deadline - time.time()}")
    current_url = url
    quiz_count = 0

    while current_url and time.time() < deadline:
        try:
            quiz_count += 1
            logger.info(f"Processing quiz {quiz_count}, URL: {current_url}")
            result = await solve_single_quiz(current_url, email, secret, deadline)

            correct = result.get("correct", False)
            next_url = result.get("url")

            logger.info(f"Quiz {quiz_count} result - Correct: {correct}, Next URL: {next_url}")

            if correct:
                if next_url:
                    logger.info(f"Correct answer, moving to next quiz: {next_url}")
                    current_url = next_url
                    continue
                else:
                    # Quiz chain finished
                    logger.info("Quiz chain completed successfully")
                    break
            else:
                # Wrong answer
                if next_url:
                    logger.warning(f"Wrong answer, skipping to next quiz: {next_url}")
                    # Skip to next
                    current_url = next_url
                else:
                    logger.error("Wrong answer with no next URL, stopping quiz chain")
                    # Stop on wrong answer with no new URL
                    break
        except Exception as e:
            # Log error and break
            logger.error(f"Error processing quiz: {e}", exc_info=True)
            break

    logger.info("Quiz chain processing completed")