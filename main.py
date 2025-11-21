# main.py
import asyncio
import time
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from settings import QUIZ_SECRET, QUIZ_EMAIL, validate_settings
from quiz_runner import run_quiz

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    validate_settings()
    logger.info("Application started and settings validated")

@app.post("/")
async def solve(request: Request):
    try:
        payload = await request.json()
        logger.info(f"Received request with payload: {payload}")
    except Exception as e:
        logger.error(f"Invalid JSON in request: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    email = payload.get("email")
    secret = payload.get("secret")
    url = payload.get("url")

    if not isinstance(email, str) or not isinstance(secret, str) or not isinstance(url, str):
        logger.warning(f"Invalid fields in request: email={type(email)}, secret={type(secret)}, url={type(url)}")
        raise HTTPException(status_code=400, detail="Missing or invalid fields")

    if secret != QUIZ_SECRET or email != QUIZ_EMAIL:
        logger.warning(f"Unauthorized access attempt: email={email}, secret matches={secret == QUIZ_SECRET}")
        raise HTTPException(status_code=403, detail="Forbidden")

    logger.info(f"Valid request received: email={email}, url={url}")

    # Deadline: 3 minutes from now
    deadline = time.time() + 180

    # fire-and-forget async task to handle quiz chain
    logger.info("Starting quiz processing task")
    asyncio.create_task(run_quiz(url=url, email=email, secret=secret, deadline=deadline))

    # Respond immediately
    logger.info("Returning accepted response")
    return JSONResponse({"status": "accepted"})