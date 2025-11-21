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
  - page_text: full text of the quiz page.
- Use only numpy and pandas operations; they are already imported as `import numpy as np` and `import pandas as pd`.
- No external network calls.
- Return the final `answer` in a type consistent with the question (number/string/boolean/json-serializable).
- Do not print anything.
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

Produce JSON with 'explanation' and 'code' fields as specified.
"""
    try:
        raw = await call_llm(PYTHON_SOLVER_SYSTEM, user_prompt)
        obj = json.loads(raw)
        logger.info("Successfully generated solver code")
        return obj["code"]
    except Exception as e:
        logger.error(f"Error generating solver code: {e}")
        raise


def describe_data_structures(data: Dict[str, Any]) -> str:
    """
    Produce a short text description of the loaded data for the LLM:
    - For DataFrames: show shape and column names.
    - For PDFs: number of pages and number of tables.
    """
    logger.info(f"Describing data structures for {len(data)} data sources")
    lines = []
    for url, obj in data.items():
        if hasattr(obj, "head"):  # assume DataFrame-like
            cols = list(obj.columns)
            logger.info(f"  {url}: DataFrame shape={obj.shape}, columns={cols}")
            lines.append(f"{url}: DataFrame shape={obj.shape}, columns={cols}")
        elif isinstance(obj, dict) and "texts" in obj and "tables" in obj:
            num_pages = len(obj["texts"])
            logger.info(f"  {url}: PDF with {num_pages} pages")
            lines.append(f"{url}: PDF with {num_pages} pages")
        else:
            logger.info(f"  {url}: Unrecognized object of type {type(obj)}")
            lines.append(f"{url}: Unrecognized object of type {type(obj)}")
    result = "\n".join(lines)
    logger.debug(f"Data description: {result}")
    return result


def run_solver_code(code: str, data: Dict[str, Any], page_text: str) -> Any:
    """
    Execute the LLM-generated code defining solve(data, page_text)
    and return the answer.
    """
    logger.info("Executing solver code")
    logger.debug(f"Code to execute: {code[:200]}...")

    # Restricted globals
    global_env = {
        "__builtins__": __builtins__,  # for assignment okay, but note security tradeoff in viva
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
        result = solve_fn(data, page_text)
        logger.info(f"Solver function returned result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error executing solver code: {e}")
        logger.debug(f"Error executing code: {code}", exc_info=True)
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
        logger.info(f"Successfully fetched quiz page, text length: {len(page_text)}")
    except Exception as e:
        logger.error(f"Error fetching quiz page: {e}")
        raise

    # Plan the solution
    logger.info("Planning solution from page text")
    try:
        plan = await plan_from_page_text(page_text)
        logger.info(f"Successfully created plan: {plan.get('question_summary', 'N/A')[:50]}...")
    except Exception as e:
        logger.error(f"Error planning from page text: {e}")
        raise

    submit_url = plan.get("submit_url")
    file_urls = plan.get("file_urls", [])
    answer_type = plan.get("answer_type")
    answer_json_template = plan.get("answer_json_template", {})

    logger.info(f"Plan details - Submit URL: {submit_url}, File URLs: {len(file_urls)}, Answer type: {answer_type}")

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
    else:
        logger.info("No files to download")

    # Generate and run solver code
    data_descr = describe_data_structures(data)
    logger.info("Generating solver code")
    try:
        solver_code = await make_solver_code(plan.get("question_summary", ""), page_text, data_descr)
        logger.info("Running solver code")
        answer = run_solver_code(solver_code, data, page_text)
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
    payload = answer_json_template.copy()
    payload.update({
        "email": email,
        "secret": secret,
        "url": url,
        "answer": answer
    })
    logger.info(f"Built payload with keys: {list(payload.keys())}")

    # Submit the answer
    logger.info(f"Submitting answer to {submit_url}")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(submit_url, json=payload)
            result = resp.json()
            logger.info(f"Received submission result: {result}")
            return result
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