# agent.py
import logging
import time
import httpx
from typing import Dict, Any, Optional

from tools import scrape_web_page, download_file, compute_answer, visualize_data
from gemini_client import call_gemini

logger = logging.getLogger(__name__)

# System prompt for the agent
AGENT_SYSTEM_PROMPT = """You are an autonomous quiz-solving agent. Your task is to:

1. Analyze quiz instructions and requirements
2. Decide which tools to use:
   - scrape_web_page: Fetch quiz pages with JavaScript rendering
   - download_file: Download CSV, Excel, PDF, or JSON data files
   - visualize_data: Generate summaries of loaded data
   - compute_answer: Generate and execute Python code to compute answers
3. Submit answers to quiz endpoints
4. Navigate through quiz chains until completion

You have access to the following tools:
- scrape_web_page(url): Scrapes a web page and returns HTML and text
- download_file(url, email=None, secret=None): Downloads and loads data files
- visualize_data(data, visualization_type="summary"): Generates data summaries
- compute_answer(question_summary, page_text, data_description, data): Computes answers using LLM-generated code

Always think step by step and use the appropriate tools to solve each quiz question."""

async def analyze_instructions(page_text: str, url: str) -> Dict[str, Any]:
    """
    Analyze quiz instructions using Gemini to determine what needs to be done.
    
    Returns a plan with:
    - question_summary: What is being asked
    - submit_url: Where to submit the answer
    - file_urls: URLs of data files to download
    - api_urls: API endpoints that need authentication
    - answer_type: Expected answer type
    - answer_json_template: Template for submission payload
    """
    logger.info("Analyzing quiz instructions")
    
    prompt = f"""You are analyzing a quiz page to extract requirements.

Quiz page URL: {url}

Page text:
{page_text}

Extract the following information as JSON:
{{
  "question_summary": "short description of what is being asked",
  "submit_url": "https://...",
  "answer_type": "number|string|boolean|json|file",
  "file_urls": ["https://..."],
  "api_urls": ["https://..."],
  "answer_json_template": {{
    "email": "",
    "secret": "",
    "url": "",
    "answer": null
  }}
}}

Rules:
- Resolve relative URLs to absolute URLs based on the page URL
- If you see relative URLs like "/data/file.csv", convert them to absolute URLs
- Include API endpoints that require authentication in api_urls
- Output only valid JSON, no markdown formatting or code blocks."""

    try:
        response = await call_gemini(AGENT_SYSTEM_PROMPT, prompt)
        
        # Clean and parse JSON
        cleaned = response.strip()
        if cleaned.startswith("```"):
            import re
            match = re.search(r'```(?:json)?\s*\n?(.*?)(?:\n?)```', cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()
        
        import re
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            json_str = json_match.group(0).strip()
        else:
            json_str = cleaned
        
        import json
        plan = json.loads(json_str)
        logger.info(f"Extracted plan: {plan.get('question_summary', 'N/A')[:50]}...")
        return plan
        
    except Exception as e:
        logger.error(f"Error analyzing instructions: {e}", exc_info=True)
        raise

async def solve_quiz_step(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single step in the quiz solving process.
    """
    url = state.get("current_url")
    email = state.get("email")
    secret = state.get("secret")
    deadline = state.get("deadline", time.time() + 180)
    
    if time.time() >= deadline:
        logger.warning("Deadline exceeded")
        state["status"] = "timeout"
        return state
    
    logger.info(f"Solving quiz step: {url}")
    
    try:
        # Step 1: Scrape the page
        page_data = await scrape_web_page(url)
        html = page_data["html"]
        page_text = page_data["text"]
        
        # Step 2: Analyze instructions
        plan = await analyze_instructions(page_text, url)
        
        # Step 3: Download files if needed
        data = {}
        if plan.get("file_urls"):
            for file_url in plan["file_urls"]:
                file_data = await download_file(file_url, email, secret)
                data[file_url] = file_data["data"]
        
        # Step 4: Fetch API data if needed
        if plan.get("api_urls"):
            async with httpx.AsyncClient(timeout=60) as client:
                for api_url in plan["api_urls"]:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(api_url)
                    query = urllib.parse.parse_qs(parsed.query)
                    query['email'] = [email]
                    query['secret'] = [secret]
                    new_query = urllib.parse.urlencode(query, doseq=True)
                    final_url = urllib.parse.urlunparse((
                        parsed.scheme, parsed.netloc, parsed.path,
                        parsed.params, new_query, parsed.fragment
                    ))
                    resp = await client.get(final_url)
                    resp.raise_for_status()
                    data[api_url] = resp.json()
        
        # Add auth context
        data['email'] = email
        data['secret'] = secret
        data['current_url'] = url
        
        # Step 5: Generate data description
        data_description = _describe_data(data)
        
        # Step 6: Compute answer
        answer = await compute_answer(
            plan.get("question_summary", ""),
            page_text,
            data_description,
            data
        )
        
        # Step 7: Submit answer
        submit_url = plan.get("submit_url", url)
        if not any(endpoint in submit_url for endpoint in ['/submit', '/api/']):
            # Try default submit endpoint
            from urllib.parse import urljoin
            submit_url = urljoin(url, "/submit")
        
        payload = plan.get("answer_json_template", {}).copy()
        payload.update({
            "email": email,
            "secret": secret,
            "url": url,
            "answer": answer
        })
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(submit_url, json=payload)
            resp.raise_for_status()
            result = resp.json()
        
        state["last_result"] = result
        state["current_url"] = result.get("url")
        state["correct"] = result.get("correct", False)
        
        logger.info(f"Submitted answer, correct: {result.get('correct')}, next URL: {result.get('url')}")
        
    except Exception as e:
        logger.error(f"Error in quiz step: {e}", exc_info=True)
        state["status"] = "error"
        state["error"] = str(e)
    
    return state

def _describe_data(data: Dict[str, Any]) -> str:
    """Generate a description of data structures."""
    lines = []
    for url, obj in data.items():
        if url in ['email', 'secret', 'current_url']:
            lines.append(f"{url}: Authentication context")
        elif hasattr(obj, "shape"):  # DataFrame
            lines.append(f"{url}: DataFrame shape={obj.shape}, columns={list(obj.columns)}")
        elif isinstance(obj, dict) and "texts" in obj:
            lines.append(f"{url}: PDF with {len(obj['texts'])} pages")
        elif isinstance(obj, dict):
            lines.append(f"{url}: JSON with keys={list(obj.keys())}")
        elif isinstance(obj, list):
            lines.append(f"{url}: List with {len(obj)} items")
        else:
            lines.append(f"{url}: {type(obj).__name__}")
    return "\n".join(lines)

async def run_quiz_chain(url: str, email: str, secret: str, deadline: float):
    """
    Run the complete quiz chain using the agent.
    """
    logger.info(f"Starting quiz chain: {url}")
    
    state: Dict[str, Any] = {
        "current_url": url,
        "email": email,
        "secret": secret,
        "deadline": deadline,
        "status": "running"
    }
    
    quiz_count = 0
    max_quizzes = 50  # Safety limit
    
    while state.get("current_url") and time.time() < deadline and quiz_count < max_quizzes:
        quiz_count += 1
        logger.info(f"Processing quiz {quiz_count}")
        
        state = await solve_quiz_step(state)
        
        if state.get("status") in ["timeout", "error"]:
            break
        
        if not state.get("current_url"):
            logger.info("Quiz chain completed")
            break
        
        if not state.get("correct") and not state.get("current_url"):
            logger.warning("Wrong answer with no next URL")
            break
    
    logger.info(f"Quiz chain finished after {quiz_count} quizzes")

