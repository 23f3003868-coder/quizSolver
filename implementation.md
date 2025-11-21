Here’s an **implementation plan in markdown** that you can drop straight into Cursor as `execution_plan.md` (or similar) and let it build from there.

---

# LLM Analysis Quiz Solver — Implementation Plan (for Cursor)

## 0. Goals & Constraints

We need a web service that:

* Exposes a **single POST endpoint** (e.g. `/` or `/solve`) that the professor’s system can call.
* Validates:

  * JSON shape
  * `email`
  * `secret`
* Returns:

  * `200` JSON for valid requests
  * `400` for invalid JSON / missing fields
  * `403` for wrong secret or mismatching email
* For valid requests, **within 3 minutes**:

  * Open the quiz URL (JS-rendered HTML, so use a **headless browser**)
  * Understand the problem
  * Download any referenced data (CSV / Excel / PDF / etc.)
  * Compute the answer (using Python + LLM help via **OpenRouter**)
  * POST the answer to the **submit URL given on the quiz page**
  * If response includes a new `url`, repeat until done or time runs out.

Hosting: **Render**
LLM: **OpenRouter**, model `deepseek/deepseek-chat-v3-0324:free` for now.

---

## 1. Tech Stack & Dependencies

**Language & Framework**

* Python 3.11
* FastAPI (web server)
* Uvicorn (ASGI server)

**HTTP & async**

* `httpx` for outgoing HTTP requests (LLM, submit URLs, file downloads)

**Browser automation (JS-rendered pages)**

* `playwright` (async API, Chromium)

**Data processing**

* `pandas` (CSV / Excel)
* `pdfplumber` (PDF table/text extraction)

**LLM**

* OpenRouter Chat Completions API

**Other**

* `python-dotenv` (local dev only, optional)

**Cursor: create `pyproject.toml` or `requirements.txt` with at least:**

```txt
fastapi
uvicorn
httpx
playwright
pandas
pdfplumber
python-dotenv
```

And in Render build command, we’ll also need:

```bash
playwright install --with-deps chromium
```

---

## 2. Repository Structure

Cursor: set up the repo like this:

```text
.
├─ main.py                 # FastAPI app entrypoint
├─ quiz_runner.py          # Quiz orchestration logic (loop over URLs)
├─ browser_utils.py        # Playwright helpers for rendering quiz pages
├─ openrouter_client.py    # OpenRouter API client wrapper
├─ data_utils.py           # File download & parsing (CSV/Excel/PDF)
├─ planner.py              # LLM-based planner for each quiz page
├─ settings.py             # Config/env variables
├─ requirements.txt        # or pyproject.toml
├─ README.md
├─ render.yaml             # Optional Render config
└─ LICENSE                 # MIT
```

---

## 3. Configuration & Environment Variables

Cursor: create `settings.py`:

```python
# settings.py
import os

QUIZ_SECRET = os.getenv("QUIZ_SECRET", "")
QUIZ_EMAIL = os.getenv("QUIZ_EMAIL", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")

# Safety: assert presence in runtime, but don't crash on import
def validate_settings():
    if not QUIZ_SECRET:
        raise RuntimeError("QUIZ_SECRET not set")
    if not QUIZ_EMAIL:
        raise RuntimeError("QUIZ_EMAIL not set")
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set")
```

On Render, set **Environment variables**:

* `QUIZ_SECRET`
* `QUIZ_EMAIL`
* `OPENROUTER_API_KEY`

---

## 4. FastAPI App & Endpoint

Cursor: implement **`main.py`**:

```python
# main.py
import asyncio
import time

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from settings import QUIZ_SECRET, QUIZ_EMAIL, validate_settings
from quiz_runner import run_quiz

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    validate_settings()

@app.post("/")
async def solve(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    email = payload.get("email")
    secret = payload.get("secret")
    url = payload.get("url")

    if not isinstance(email, str) or not isinstance(secret, str) or not isinstance(url, str):
        raise HTTPException(status_code=400, detail="Missing or invalid fields")

    if secret != QUIZ_SECRET or email != QUIZ_EMAIL:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Deadline: 3 minutes from now
    deadline = time.time() + 180

    # fire-and-forget async task to handle quiz chain
    asyncio.create_task(run_quiz(url=url, email=email, secret=secret, deadline=deadline))

    # Respond immediately
    return JSONResponse({"status": "accepted"})
```

This ensures professor gets a quick HTTP 200 while the quiz is processed **in the background**.

---

## 5. OpenRouter Client

Cursor: implement **`openrouter_client.py`**:

```python
# openrouter_client.py
import httpx
from settings import OPENROUTER_API_KEY, OPENROUTER_MODEL

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    # Optional but recommended by OpenRouter:
    "HTTP-Referer": "https://your-render-service-url",  # replace at deploy time
    "X-Title": "TDS LLM Quiz Solver",
}

async def call_llm(system_prompt: str, user_prompt: str, *, temperature: float = 0.0, model: str | None = None) -> str:
    payload = {
        "model": model or OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(OPENROUTER_URL, headers=HEADERS, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
```

---

## 6. Browser Utilities (Playwright)

Cursor: implement **`browser_utils.py`**:

```python
# browser_utils.py
from playwright.async_api import async_playwright

async def fetch_quiz_page(url: str) -> tuple[str, str]:
    """
    Returns (html, text) of the fully rendered quiz page.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        html = await page.content()
        text = await page.inner_text("body")
        await browser.close()
    return html, text
```

---

## 7. Planner: LLM to Structure the Task

We’ll use the LLM to create a **structured JSON plan** for each quiz page.

Cursor: implement **`planner.py`**:

```python
# planner.py
import json
from openrouter_client import call_llm

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
    user_prompt = (
        "Here is the full text content of the quiz page:\n\n"
        f"{page_text}\n\n"
        "Extract the JSON plan as specified."
    )
    raw = await call_llm(PLANNER_SYSTEM_PROMPT, user_prompt)
    return json.loads(raw)
```

---

## 8. Data Utilities (file download + parsing)

Cursor: implement **`data_utils.py`**:

```python
# data_utils.py
import os
import tempfile
from typing import Dict, Any, List

import httpx
import pandas as pd
import pdfplumber

async def download_files(file_urls: list[str]) -> dict[str, str]:
    """
    Download each URL to a temp file.
    Returns mapping: {url: local_path}
    """
    downloaded: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=60) as client:
        for url in file_urls:
            resp = await client.get(url)
            resp.raise_for_status()
            suffix = guess_suffix_from_url(url)
            fd, path = tempfile.mkstemp(suffix=suffix)
            with os.fdopen(fd, "wb") as f:
                f.write(resp.content)
            downloaded[url] = path
    return downloaded

def guess_suffix_from_url(url: str) -> str:
    for ext in [".csv", ".xlsx", ".xls", ".pdf"]:
        if url.lower().endswith(ext):
            return ext
    return ""

def load_dataframes(downloaded: dict[str, str]) -> dict[str, Any]:
    """
    Load downloaded files into pandas / pdfplumber structures.
    Returns mapping: {url: data}
    where data is:
      - pandas.DataFrame for CSV/Excel
      - dict with pdf info for PDFs
    """
    result: dict[str, Any] = {}
    for url, path in downloaded.items():
        if path.endswith(".csv"):
            result[url] = pd.read_csv(path)
        elif path.endswith((".xlsx", ".xls")):
            result[url] = pd.read_excel(path)
        elif path.endswith(".pdf"):
            # For now: extract tables for each page
            with pdfplumber.open(path) as pdf:
                tables: List = []
                texts: List[str] = []
                for page in pdf.pages:
                    texts.append(page.extract_text() or "")
                    page_tables = page.extract_tables() or []
                    tables.append(page_tables)
                result[url] = {
                    "texts": texts,
                    "tables": tables,  # list[page][table][rows]
                }
        else:
            # Unknown type, keep raw path
            result[url] = {"path": path}
    return result
```

---

## 9. Computing the Answer

We’ll use the LLM as a **code generator** for transformations over loaded data.

Cursor: in **`quiz_runner.py`**, we’ll add helpers to:

* Call the planner and data utils
* Ask LLM to produce a Python `solve(data, page_text)` function
* Execute it and get the `answer`

### 9.1 LLM Code Generator

Add to `quiz_runner.py` (or `solver_llm.py` if you prefer):

```python
import json
from typing import Any, Dict

from openrouter_client import call_llm

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
    user_prompt = f"""
Question summary:
{question_summary}

Quiz page text:
{page_text}

Data description:
{data_descr}

Produce JSON with 'explanation' and 'code' fields as specified.
"""
    raw = await call_llm(PYTHON_SOLVER_SYSTEM, user_prompt)
    obj = json.loads(raw)
    return obj["code"]
```

### 9.2 Building the `data_descr` String

Cursor: add helper in `quiz_runner.py`:

```python
def describe_data_structures(data: Dict[str, Any]) -> str:
    """
    Produce a short text description of the loaded data for the LLM:
    - For DataFrames: show shape and column names.
    - For PDFs: number of pages and number of tables.
    """
    lines = []
    for url, obj in data.items():
        if hasattr(obj, "head"):  # assume DataFrame-like
            cols = list(obj.columns)
            lines.append(f"{url}: DataFrame shape={obj.shape}, columns={cols}")
        elif isinstance(obj, dict) and "texts" in obj and "tables" in obj:
            num_pages = len(obj["texts"])
            lines.append(f"{url}: PDF with {num_pages} pages")
        else:
            lines.append(f"{url}: Unrecognized object of type {type(obj)}")
    return "\n".join(lines)
```

### 9.3 Executing Generated Code Safely (ish)

Cursor: still in `quiz_runner.py`, add:

```python
import types
import numpy as np
import pandas as pd

def run_solver_code(code: str, data: Dict[str, Any], page_text: str) -> Any:
    """
    Execute the LLM-generated code defining solve(data, page_text)
    and return the answer.
    """
    # Restricted globals
    global_env = {
        "__builtins__": __builtins__,  # for assignment okay, but note security tradeoff in viva
        "pd": pd,
        "np": np,
    }
    local_env: dict = {}
    exec(code, global_env, local_env)
    solve_fn = local_env.get("solve")
    if not isinstance(solve_fn, types.FunctionType):
        raise RuntimeError("No solve(data, page_text) function found")
    return solve_fn(data, page_text)
```

You can mention in viva: **this is not fully secure** but acceptable for controlled assignment; in production you’d sandbox.

---

## 10. Quiz Orchestrator Logic

Cursor: implement **`quiz_runner.py`** to tie everything together:

```python
# quiz_runner.py
import time
from typing import Any, Dict

import httpx

from browser_utils import fetch_quiz_page
from planner import plan_from_page_text
from data_utils import download_files, load_dataframes
from . import  # ensure imports from solver helpers above

async def solve_single_quiz(url: str, email: str, secret: str, deadline: float) -> Dict[str, Any]:
    if time.time() >= deadline:
        return {"correct": False, "reason": "Deadline exceeded before starting"}

    html, page_text = await fetch_quiz_page(url)
    plan = await plan_from_page_text(page_text)

    submit_url = plan["submit_url"]
    file_urls = plan.get("file_urls", []) or []
    answer_type = plan.get("answer_type", "string")
    template = plan["answer_json_template"]

    # 1) Download + load data
    downloaded = await download_files(file_urls)
    data = load_dataframes(downloaded)
    data_descr = describe_data_structures(data)

    # 2) Get solver code from LLM
    solver_code = await make_solver_code(
        question_summary=plan["question_summary"],
        page_text=page_text,
        data_descr=data_descr,
    )

    # 3) Run solver code to get answer
    answer = run_solver_code(solver_code, data, page_text)

    # Optional: cast based on answer_type
    if answer_type == "number":
        try:
            answer = float(answer)
        except Exception:
            # leave as-is; quiz may expect stringified number
            pass

    # 4) Fill payload based on template
    payload = template.copy()
    payload["email"] = email
    payload["secret"] = secret
    payload["url"] = url
    payload["answer"] = answer

    # 5) Submit to submit_url
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(submit_url, json=payload)
    resp.raise_for_status()
    result = resp.json()
    return result

async def run_quiz(url: str, email: str, secret: str, deadline: float):
    current_url = url

    while current_url and time.time() < deadline:
        try:
            result = await solve_single_quiz(current_url, email, secret, deadline)
        except Exception as e:
            # Log error; cannot print easily, but we can use print for Render logs
            print(f"Error solving quiz at {current_url}: {e}")
            break

        correct = result.get("correct", False)
        next_url = result.get("url")

        if correct:
            print(f"Solved quiz {current_url} correctly.")
            if next_url:
                current_url = next_url
                continue
            else:
                print("Quiz chain finished.")
                break
        else:
            print(f"Incorrect answer for {current_url}: {result.get('reason')}")
            if next_url:
                # Professor's spec: allowed to skip ahead if new URL is given
                current_url = next_url
                continue
            else:
                # Optionally: reattempt once, but we keep it simple
                break
```

---

## 11. Render Deployment

Cursor: add a **`render.yaml`** (optional, helps infra-as-code):

```yaml
services:
  - type: web
    name: tds-llm-quiz-solver
    env: python
    plan: free
    buildCommand: |
      pip install -r requirements.txt
      python -m playwright install --with-deps chromium
    startCommand: |
      uvicorn main:app --host 0.0.0.0 --port 10000
    envVars:
      - key: QUIZ_SECRET
        sync: false
      - key: QUIZ_EMAIL
        sync: false
      - key: OPENROUTER_API_KEY
        sync: false
```

In Render dashboard:

1. Connect the GitHub repo (public or private).
2. Set environment variables (`QUIZ_SECRET`, `QUIZ_EMAIL`, `OPENROUTER_API_KEY`).
3. Deploy.

Your final endpoint will be something like:

```text
https://tds-llm-quiz-solver.onrender.com/
```

This is what you put into the **Google Form** as the API endpoint.

---

## 12. Local Testing

Cursor: create a basic test script (or just use curl):

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
        "email": "YOUR_EMAIL_HERE",
        "secret": "YOUR_SECRET_HERE",
        "url": "https://tds-llm-analysis.s-anand.net/demo"
      }'
```

Run locally:

```bash
uvicorn main:app --reload
```

Watch the logs to see if:

* Page loads via Playwright
* Planner LLM returns JSON (fix prompt if invalid JSON)
* Data downloads succeed
* Solver code executes and submits to the demo endpoint.

---

## 13. Viva Talking Points (for later)

Not for Cursor, but for you:

* You separated concerns:

  * **API layer** (FastAPI) for validation + deadline management
  * **Browser layer** (Playwright) for JS-rendered HTML
  * **Planner LLM** to convert messy text to structured plan
  * **Data layer** (pandas + pdfplumber) for actual computation
  * **Solver LLM** as code generator for complex data questions
* You handle chained quiz URLs and respect the **3-minute** deadline.
* You chose OpenRouter because you can swap models and use free/cheap models like `deepseek/deepseek-chat-v3-0324:free`.

---

If you want, next I can help you **shrink this into a shorter “Cursor tasks checklist”** or tweak the planner/solver prompts to be more jailbreak-resistant / robust.
