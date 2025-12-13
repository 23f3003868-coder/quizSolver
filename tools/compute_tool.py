# tools/compute_tool.py
import logging
import json
import types
from typing import Dict, Any
import numpy as np
import pandas as pd
from gemini_client import call_gemini

logger = logging.getLogger(__name__)

COMPUTE_SYSTEM_PROMPT = """You are a Python data analysis assistant.

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

async def compute_answer(question_summary: str, page_text: str, data_description: str, data: Dict[str, Any]) -> Any:
    """
    Compute the answer to a quiz question using LLM-generated Python code.
    
    Args:
        question_summary: Summary of what the question is asking
        page_text: Full text content of the quiz page
        data_description: Description of available data structures
        data: Dictionary mapping URLs to loaded data objects
        
    Returns:
        The computed answer
    """
    logger.info(f"Computing answer for question: {question_summary[:50]}...")
    
    user_prompt = f"""
Question summary:
{question_summary}

Quiz page text:
{page_text}

Data description:
{data_description}

Produce JSON with 'explanation' and 'code' fields as specified. Do not include any markdown formatting, code blocks, or extra text - only return valid JSON.
"""
    
    try:
        raw_response = await call_gemini(COMPUTE_SYSTEM_PROMPT, user_prompt)
        
        # Clean up response to extract JSON
        cleaned_response = raw_response.strip()
        
        # Handle markdown code blocks
        if cleaned_response.startswith("```"):
            import re
            match = re.search(r'```(?:json)?\s*\n?(.*?)(?:\n?)```', cleaned_response, re.DOTALL)
            if match:
                cleaned_response = match.group(1).strip()
        
        # Extract JSON object
        import re
        json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0).strip()
        else:
            json_str = cleaned_response
        
        obj = json.loads(json_str)
        code = obj["code"]
        
        logger.info("Generated solver code, executing...")
        
        # Execute the code
        global_env = {
            "__builtins__": __builtins__,
            "pd": pd,
            "np": np,
        }
        local_env = {}
        
        exec(code, global_env, local_env)
        solve_fn = local_env.get("solve")
        
        if not isinstance(solve_fn, types.FunctionType):
            raise RuntimeError("No solve(data, page_text) function found in generated code")
        
        # Call the solve function
        result = solve_fn(data, page_text)
        
        logger.info(f"Successfully computed answer: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error computing answer: {e}", exc_info=True)
        raise

