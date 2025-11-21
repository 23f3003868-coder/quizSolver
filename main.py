# main.py
import asyncio
import time
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from settings import QUIZ_SECRET, QUIZ_EMAIL, validate_settings
from quiz_runner import run_quiz

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

@app.get("/demo", response_class=HTMLResponse)
async def demo_quiz_page():
    """
    Demo quiz page that demonstrates the type of quiz the solver should handle.
    This page includes a sample question and data file that the solver needs to process.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Quiz Solver Demo</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .question {
                margin: 20px 0;
                padding: 15px;
                background-color: #f9f9f9;
                border-left: 4px solid #007cba;
            }
            .instructions {
                background-color: #e7f3ff;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
            }
            button {
                background-color: #007cba;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                margin: 10px 5px;
            }
            button:hover {
                background-color: #005a87;
            }
            .response {
                margin-top: 20px;
                padding: 15px;
                border-radius: 5px;
                background-color: #f0f0f0;
            }
            .hidden {
                display: none;
            }
            .success {
                background-color: #d4edda;
                color: #155724;
                border: 1px solid #c3e6cb;
            }
            .error {
                background-color: #f8d7da;
                color: #721c24;
                border: 1px solid #f5c6cb;
            }
            .quiz-content {
                margin: 20px 0;
            }
            .quiz-content h3 {
                color: #007cba;
            }
            .answer-input {
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Quiz Solver Test Page</h1>

            <div class="instructions">
                <h3>Quiz Instructions</h3>
                <p>This is a demo quiz page to test your quiz solver. Your solver should:</p>
                <ol>
                    <li>Read the question below</li>
                    <li>Download and analyze any provided data files</li>
                    <li>Calculate the correct answer</li>
                    <li>Submit the answer to this page's submit endpoint</li>
                </ol>
            </div>

            <div class="question">
                <h3>Quiz Question #1</h3>
                <div class="quiz-content">
                    <p>Download the <a href="/data/quiz-data.csv" id="data-link">CSV data file</a> and calculate the average of the "value" column.</p>
                    <p>What is the average of the "value" column in the CSV file?</p>
                </div>

                <div>
                    <label for="answer">Your Answer:</label>
                    <input type="text" id="answer" class="answer-input" placeholder="Enter your calculated answer">
                    <div>
                        <button onclick="submitAnswer()">Submit Answer</button>
                        <button onclick="skipQuiz()">Skip to Next Quiz</button>
                    </div>
                </div>
            </div>

            <div id="response" class="response hidden"></div>
        </div>

        <script>
            // Function to submit answer
            function submitAnswer() {
                const answer = document.getElementById('answer').value;
                if (!answer) {
                    showResponse('Please enter an answer', 'error');
                    return;
                }

                // Submit to quiz endpoint
                const quizData = {
                    email: "23f3003868@ds.study.iitm.ac.in",
                    secret: "495669",
                    url: window.location.href,
                    answer: parseFloat(answer) || answer
                };

                fetch('/submit', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(quizData)
                })
                .then(response => response.json())
                .then(data => {
                    if (data.correct) {
                        showResponse(`Correct! ${data.reason || 'Moving to next quiz...'}`, 'success');
                        if (data.url) {
                            setTimeout(() => {
                                window.location.href = data.url;
                            }, 2000);
                        }
                    } else {
                        showResponse(`Incorrect: ${data.reason || 'Please try again.'}`, 'error');
                    }
                })
                .catch(error => {
                    showResponse(`Error submitting answer: ${error.message}`, 'error');
                });
            }

            // Function to skip to next quiz
            function skipQuiz() {
                // In a real scenario, you might have logic to get the next quiz URL
                showResponse('Skipping to next quiz...', 'success');
                setTimeout(() => {
                    window.location.href = '/next'; // Placeholder
                }, 1000);
            }

            // Function to show response
            function showResponse(message, type) {
                const responseDiv = document.getElementById('response');
                responseDiv.textContent = message;
                responseDiv.className = `response ${type}`;
                responseDiv.classList.remove('hidden');
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/data/quiz-data.csv")
async def get_quiz_data():
    """
    Endpoint to serve the quiz data file for the demo.
    """
    csv_content = """name,value,category
John,10,A
Jane,20,B
Bob,30,A
Alice,40,B
Charlie,50,A"""
    return Response(content=csv_content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=quiz-data.csv"})

@app.post("/submit")
async def submit_quiz(request: Request):
    """
    Demo submission endpoint that validates answers for the demo quiz.
    """
    try:
        payload = await request.json()
        logger.info(f"Received quiz submission: {payload}")

        # For the demo, the correct answer is the average of [10, 20, 30, 40, 50] = 30
        correct_answer = 30

        submitted_answer = payload.get("answer")
        if submitted_answer == correct_answer or (isinstance(submitted_answer, (int, float)) and abs(submitted_answer - correct_answer) < 0.01):
            # Correct answer
            response = {
                "correct": True,
                "reason": "Great job! That's the correct average.",
                "url": None  # No next quiz in demo
            }
        else:
            # Incorrect answer
            response = {
                "correct": False,
                "reason": f"Incorrect answer. Expected {correct_answer}, got {submitted_answer}"
            }

        logger.info(f"Returning submission result: {response}")
        return JSONResponse(response)
    except Exception as e:
        logger.error(f"Error processing quiz submission: {e}")
        raise HTTPException(status_code=400, detail="Invalid submission data")