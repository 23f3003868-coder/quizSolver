Here’s a **concrete, step-by-step task list** you can feed to Qwen CLI coder to build the project.

I’ll assume:

* Python project
* FastAPI app
* Deployed on Render
* Single POST endpoint at `/`

You can paste this as a “dev plan” or “tasks list” for Qwen.

---

## 1. Initialize project structure

1. Create a new Python project with this structure:

   ```text
   .
   ├─ main.py                 # FastAPI app
   ├─ quiz_runner.py          # Quiz orchestration logic
   ├─ browser_utils.py        # Playwright helpers
   ├─ openrouter_client.py    # OpenRouter wrapper
   ├─ data_utils.py           # Download + parse data files
   ├─ planner.py              # LLM planner for each quiz page
   ├─ settings.py             # Config + env vars
   ├─ requirements.txt
   ├─ render.yaml             # Render deployment config
   ├─ README.md
   └─ LICENSE                 # MIT
   ```

2. Initialize a git repo, add `MIT` license, and basic `README.md` explaining the assignment briefly.

---

## 2. Dependencies

3. Create `requirements.txt` with at least:

   ```txt
   fastapi
   uvicorn
   httpx
   playwright
   pandas
   pdfplumber
   python-dotenv
   ```

4. Ensure there’s a note in `README.md` that after installing dependencies, we must run:

   ```bash
   python -m playwright install --with-deps chromium
   ```

---

## 3. Global settings and environment config

5. Implement `settings.py`:

   * Read these environment variables:

     * `QUIZ_SECRET`
     * `QUIZ_EMAIL`
     * `OPENROUTER_API_KEY`
     * Optional: `OPENROUTER_MODEL` defaulting to `deepseek/deepseek-chat-v3-0324:free`
   * Provide a function `validate_settings()` that raises `RuntimeError` if any of the critical vars are missing.

   ```python
   # settings.py
   import os

   QUIZ_SECRET = os.getenv("QUIZ_SECRET", "")
   QUIZ_EMAIL = os.getenv("QUIZ_EMAIL", "")
   OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
   OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")

   def validate_settings():
       if not QUIZ_SECRET:
           raise RuntimeError("QUIZ_SECRET not set")
       if not QUIZ_EMAIL:
           raise RuntimeError("QUIZ_EMAIL not set")
       if not OPENROUTER_API_KEY:
           raise RuntimeError("OPENROUTER_API_KEY not set")
   ```

---

## 4. OpenRouter client

6. Implement `openrouter_client.py`:

   * Use `httpx.AsyncClient`
   * Create function `async def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.0, model: str | None = None) -> str`
   * Use `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` from `settings.py`
   * Hit `https://openrouter.ai/api/v1/chat/completions`
   * Return `str` content of first choice.

   Skeleton:

   ```python
   # openrouter_client.py
   import httpx
   from settings import OPENROUTER_API_KEY, OPENROUTER_MODEL

   OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

   HEADERS = {
       "Authorization": f"Bearer {OPENROUTER_API_KEY}",
       "HTTP-Referer": "https://your-render-service-url",  # TODO: replace in README
       "X-Title": "TDS LLM Quiz Solver",
   }

   async def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.0, model: str | None = None) -> str:
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

## 5. Browser utilities using Playwright

7. Implement `browser_utils.py`:

   * Async function `fetch_quiz_page(url: str) -> tuple[str, str]`
   * Use Playwright Chromium headless
   * `page.goto(url, wait_until="networkidle")`
   * Return `(html, text)` where `text = await page.inner_text("body")`

   ```python
   # browser_utils.py
   from playwright.async_api import async_playwright

   async def fetch_quiz_page(url: str) -> tuple[str, str]:
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

## 6. LLM planner for quiz pages

8. Implement `planner.py`:

   * Define `PLANNER_SYSTEM_PROMPT` describing the strict JSON schema:

     ```jsonc
     {
       "question_summary": "short description",
       "submit_url": "https://...",
       "answer_type": "number|string|boolean|json|file",
       "file_urls": ["..."],
       "answer_json_template": {
         "email": "",
         "secret": "",
         "url": "",
         "answer": null
       }
     }
     ```

   * Function `async def plan_from_page_text(page_text: str) -> dict`:

     * Calls `call_llm` with system + user prompts
     * Expects valid JSON in response
     * `json.loads` and return dict

   Skeleton:

   ```python
   # planner.py
   import json
   from openrouter_client import call_llm

   PLANNER_SYSTEM_PROMPT = """
   You are a planning assistant for solving data quizzes.

   You receive the FULL TEXT of a quiz webpage.

   Output a STRICT JSON object with these fields:

   {
     "question_summary": "short description of what is being asked",
     "submit_url": "https://...",
     "answer_type": "number|string|boolean|json|file",
     "file_urls": ["https://...", "..."],
     "answer_json_template": {
       "email": "",
       "secret": "",
       "url": "",
       "answer": null
     }
   }

   Rules:
   - If the page shows a JSON payload schema, copy that into answer_json_template but set the answer to null.
   - No comments or extra fields.
   - Output ONLY valid JSON, no extra text.
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

## 7. Data utilities: download and load

9. Implement `data_utils.py`:

   * `async def download_files(file_urls: list[str]) -> dict[str, str]`

     * Use `httpx.AsyncClient`
     * Save to `tempfile.mkstemp`
     * Return `{url: local_path}`

   * `def guess_suffix_from_url(url: str) -> str` handling `.csv`, `.xlsx`, `.xls`, `.pdf`.

   * `def load_dataframes(downloaded: dict[str, str]) -> dict[str, Any]`:

     * `.csv` → `pandas.read_csv`
     * `.xlsx`/`.xls` → `pandas.read_excel`
     * `.pdf` → `pdfplumber`, returning dict with `"texts"` and `"tables"` per page
     * Anything else → `{"path": path}`

   Skeleton is basically what we wrote earlier.

---

## 8. LLM-based solver code generation

10. In `quiz_runner.py` (or new `solver_llm.py`), implement:

* `PYTHON_SOLVER_SYSTEM` prompt that instructs model to output JSON with:

  ```jsonc
  {
    "explanation": "...",
    "code": "def solve(data, page_text):\n    ...\n    return answer"
  }
  ```

* Function `async def make_solver_code(question_summary: str, page_text: str, data_descr: str) -> str`:

  * Call `call_llm(PYTHON_SOLVER_SYSTEM, user_prompt)`
  * Parse JSON
  * Return `code` string

* Function `def describe_data_structures(data: dict[str, Any]) -> str`:

  * For DataFrames: include shape + column names
  * For PDFs: include number of pages

* Function `def run_solver_code(code: str, data: dict[str, Any], page_text: str) -> Any`:

  * Execute code with restricted globals:

    * `pd` (pandas), `np` (numpy)
  * Extract `solve` and call `solve(data, page_text)`
  * Return answer

Make sure to import `pandas as pd` and `numpy as np`.

---

## 9. Quiz orchestration (single quiz and loop)

11. Implement `quiz_runner.py` orchestrator:

* Function `async def solve_single_quiz(url: str, email: str, secret: str, deadline: float) -> dict`:

  Steps:

  1. If `time.time() >= deadline`: return `{"correct": False, "reason": "Deadline exceeded before starting"}`.
  2. Use `fetch_quiz_page(url)` to get `(html, page_text)`.
  3. Use `plan_from_page_text(page_text)` to get `plan`.
  4. Extract `submit_url`, `file_urls`, `answer_type`, `answer_json_template`.
  5. Download and load data via `download_files` and `load_dataframes`.
  6. Use `describe_data_structures(data)` and `make_solver_code(...)` to get `solver_code`.
  7. Run `run_solver_code(solver_code, data, page_text)` to get `answer`.
  8. Cast `answer` to numeric if `answer_type == "number"` where possible.
  9. Build payload from template:

     * Set `email`, `secret`, `url`, `answer`.
  10. POST to `submit_url` via `httpx.AsyncClient`.
  11. Return parsed JSON result.

* Function `async def run_quiz(url: str, email: str, secret: str, deadline: float)`:

  Loop:

  1. Set `current_url = url`.
  2. While `current_url` and `time.time() < deadline`:

     * Call `solve_single_quiz(current_url, email, secret, deadline)` inside `try/except`.
     * If exception: log and break.
     * Read `correct` and `next_url = result.get("url")`.
     * If `correct`:

       * If `next_url` exists → `current_url = next_url` and continue.
       * Else break (quiz chain finished).
     * If not `correct`:

       * If `next_url` exists → skip ahead (`current_url = next_url`).
       * Else break (stop on wrong answer with no new URL).

---

## 10. FastAPI entrypoint

12. Implement `main.py`:

* Import `FastAPI`, `Request`, `HTTPException`, `JSONResponse`.

* On startup, call `validate_settings()`.

* `POST "/"`:

  * Parse JSON; if fail → `400`.
  * Validate `email`, `secret`, `url` types; if invalid → `400`.
  * If secret or email mismatch env vars → `403`.
  * Compute `deadline = time.time() + 180`.
  * `asyncio.create_task(run_quiz(url=url, email=email, secret=secret, deadline=deadline))`.
  * Return `{"status": "accepted"}` with HTTP 200.

* Ready for `uvicorn main:app`.

---

## 11. Render deployment config

13. Implement `render.yaml`:

* One `web` service
* Build command: install deps + Playwright Chromium
* Start command: `uvicorn main:app --host 0.0.0.0 --port 10000`
* Configure env vars placeholders.

Example:

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

---

## 12. Local + demo testing

14. Add a short `README.md` section:

* How to run locally:

  ```bash
  pip install -r requirements.txt
  python -m playwright install --with-deps chromium

  export QUIZ_SECRET="your-secret"
  export QUIZ_EMAIL="your-email"
  export OPENROUTER_API_KEY="sk-..."
  uvicorn main:app --reload
  ```

* How to test against the provided demo endpoint:

  ```bash
  curl -X POST http://localhost:8000/ \
    -H "Content-Type: application/json" \
    -d '{
          "email": "your-email",
          "secret": "your-secret",
          "url": "https://tds-llm-analysis.s-anand.net/demo"
        }'
  ```

15. Confirm logs show quiz chain attempts and that there are no obvious exceptions.

---

You can give Qwen this plan and say:

> “Follow these steps in order and implement all missing files and functions accordingly.”

If you want, I can next compress this into an even shorter “task checklist” version (good for a single prompt) with just bullet-point actions.
