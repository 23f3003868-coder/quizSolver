# main.py
import asyncio
import time
import logging
from typing import Dict

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.responses import Response

from settings import validate_settings
from agent import run_quiz_chain

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Serve static files if needed
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    pass  # Directory may not exist yet

# Track uptime for health check
start_time = time.time()

@app.on_event("startup")
async def startup_event():
    validate_settings()
    logger.info("Application started and settings validated")

@app.post("/solve")
async def solve(request: Request):
    """
    Main endpoint to trigger the autonomous quiz solver.
    
    Request body:
    {
        "email": "your_email@ds.study.iitm.ac.in",
        "secret": "your_secret",
        "url": "https://tds-llm-analysis.s-anand.net/demo"
    }
    """
    try:
        payload = await request.json()
        logger.info(f"Received solve request")
    except Exception as e:
        logger.error(f"Invalid JSON in request: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    email = payload.get("email")
    secret = payload.get("secret")
    url = payload.get("url")

    if not isinstance(email, str) or not isinstance(secret, str) or not isinstance(url, str):
        logger.warning(f"Invalid fields in request")
        raise HTTPException(status_code=400, detail="Missing or invalid fields: email, secret, url required")

    logger.info(f"Valid request received: email={email}, url={url}")

    # Deadline: 3 minutes from now
    deadline = time.time() + 180

    # Fire-and-forget async task to handle quiz chain
    logger.info("Starting quiz processing task")
    asyncio.create_task(run_quiz_chain(url=url, email=email, secret=secret, deadline=deadline))

    # Respond immediately
    logger.info("Returning accepted response")
    return JSONResponse({
        "status": "ok",
        "message": "Processing started"
    })

@app.get("/healthz")
async def healthz():
    """
    Health check endpoint for monitoring services.
    """
    uptime = time.time() - start_time
    return JSONResponse({
        "status": "ok",
        "uptime_seconds": int(uptime)
    })
