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
        <title>Advanced Quiz Solver Demo</title>
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
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Advanced Quiz Solver Test Page</h1>

            <div class="instructions">
                <h3>Quiz Instructions</h3>
                <p>This is an advanced demo quiz page to test your quiz solver capabilities. Your solver should handle various data analysis tasks:</p>
                <ul>
                    <li>Sourcing data from multiple formats (CSV, potentially PDF)</li>
                    <li>Processing and cleansing text/data</li>
                    <li>Performing analysis by filtering, sorting, aggregating</li>
                    <li>Applying statistical models (averages, sums, counts)</li>
                </ul>
            </div>

            <div class="question">
                <h3>Quiz Question #1: Basic Aggregation</h3>
                <div class="quiz-content">
                    <p>Download the <a href="/data/quiz-data.csv" id="data-link">CSV data file</a> and calculate the average of the "value" column.</p>
                    <p>What is the average of the "value" column in the CSV file?</p>
                    <p>Data preview:</p>
                    <table>
                        <tr><th>name</th><th>value</th><th>category</th></tr>
                        <tr><td>John</td><td>10</td><td>A</td></tr>
                        <tr><td>Jane</td><td>20</td><td>B</td></tr>
                        <tr><td>Bob</td><td>30</td><td>A</td></tr>
                        <tr><td>Alice</td><td>40</td><td>B</td></tr>
                        <tr><td>Charlie</td><td>50</td><td>A</td></tr>
                    </table>
                </div>

                <div>
                    <label for="answer1">Your Answer:</label>
                    <input type="text" id="answer1" class="answer-input" placeholder="Enter your calculated answer">
                    <div>
                        <button onclick="submitAnswer(1)">Submit Answer</button>
                    </div>
                </div>
            </div>

            <div class="question">
                <h3>Quiz Question #2: Complex Analysis</h3>
                <div class="quiz-content">
                    <p>From the same CSV file, calculate the sum of values for category 'A' only.</p>
                    <p>What is the sum of 'value' column where 'category' is 'A'?</p>
                </div>

                <div>
                    <label for="answer2">Your Answer:</label>
                    <input type="text" id="answer2" class="answer-input" placeholder="Enter your calculated answer">
                    <div>
                        <button onclick="submitAnswer(2)">Submit Answer</button>
                    </div>
                </div>
            </div>

            <div class="question">
                <h3>Quiz Question #3: Statistical Analysis</h3>
                <div class="quiz-content">
                    <p>From the same CSV file, find the person with the highest value in category 'B'.</p>
                    <p>Return the name of the person with the highest value in category 'B'.</p>
                </div>

                <div>
                    <label for="answer3">Your Answer:</label>
                    <input type="text" id="answer3" class="answer-input" placeholder="Enter the name">
                    <div>
                        <button onclick="submitAnswer(3)">Submit Answer</button>
                    </div>
                </div>
            </div>

            <div id="response" class="response hidden"></div>
        </div>

        <script>
            // Function to submit answer
            function submitAnswer(questionNumber) {
                let answer;
                if (questionNumber === 1) {
                    answer = document.getElementById('answer1').value;
                } else if (questionNumber === 2) {
                    answer = document.getElementById('answer2').value;
                } else if (questionNumber === 3) {
                    answer = document.getElementById('answer3').value;
                }

                if (!answer) {
                    showResponse('Please enter an answer', 'error');
                    return;
                }

                // Submit to quiz endpoint
                const quizData = {
                    email: "23f3003868@ds.study.iitm.ac.in",
                    secret: "495669",
                    url: window.location.href,
                    answer: questionNumber === 1 || questionNumber === 2 ? parseFloat(answer) || answer : answer
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
                        showResponse(`Correct! ${data.reason || 'Well done!'}`, 'success');
                    } else {
                        showResponse(`Incorrect: ${data.reason || 'Please try again.'}`, 'error');
                    }
                })
                .catch(error => {
                    showResponse(`Error submitting answer: ${error.message}`, 'error');
                });
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

        # Load CSV data to validate various possible answers
        import io
        import pandas as pd

        # CSV content (same as in /data/quiz-data.csv)
        csv_content = """name,value,category
John,10,A
Jane,20,B
Bob,30,A
Alice,40,B
Charlie,50,A"""

        df = pd.read_csv(io.StringIO(csv_content))

        submitted_answer = payload.get("answer")

        # Determine what the question might be asking based on common patterns
        # Question 1: Average of 'value' column - should be 30
        avg_value = df['value'].mean()
        # Question 2: Sum of values where category is 'A' - should be 10+30+50 = 90
        sum_category_a = df[df['category'] == 'A']['value'].sum()
        # Question 3: Name with highest value in category 'B' - Jane with value 20, then Alice with value 40, so Alice is highest
        highest_in_b = df[df['category'] == 'B'].loc[df[df['category'] == 'B']['value'].idxmax()]['name']

        # Check for various possible correct answers based on different questions
        if (submitted_answer == avg_value or
            (isinstance(submitted_answer, (int, float)) and abs(submitted_answer - avg_value) < 0.01)):
            # Correct answer for question 1
            logger.info(f"Correct answer for Q1 submitted: {submitted_answer}")
            response = {
                "correct": True,
                "reason": "Great job! That's the correct average of the value column.",
                "url": None  # No next quiz in demo
            }
        elif (submitted_answer == sum_category_a or
              (isinstance(submitted_answer, (int, float)) and abs(submitted_answer - sum_category_a) < 0.01)):
            # Correct answer for question 2
            logger.info(f"Correct answer for Q2 submitted: {submitted_answer}")
            response = {
                "correct": True,
                "reason": "Great job! That's the correct sum of values in category A.",
                "url": None  # No next quiz in demo
            }
        elif (submitted_answer == highest_in_b or
              (isinstance(submitted_answer, str) and submitted_answer.lower() == highest_in_b.lower())):
            # Correct answer for question 3
            logger.info(f"Correct answer for Q3 submitted: {submitted_answer}")
            response = {
                "correct": True,
                "reason": f"Great job! {highest_in_b} has the highest value in category B.",
                "url": None  # No next quiz in demo
            }
        else:
            # Incorrect answer
            logger.info(f"Incorrect answer submitted: {submitted_answer}. Possible correct answers: {avg_value}, {sum_category_a}, {highest_in_b}")
            response = {
                "correct": False,
                "reason": f"Incorrect answer. Possible answers: average={avg_value}, sum of A={sum_category_a}, highest in B={highest_in_b}"
            }

        logger.info(f"Returning submission result: {response}")
        return JSONResponse(response)
    except Exception as e:
        logger.error(f"Error processing quiz submission: {e}")
        raise HTTPException(status_code=400, detail="Invalid submission data")

@app.get("/test")
async def test_endpoint():
    """
    Test endpoint to verify LLM functionality
    """
    from openrouter_client import call_llm
    from planner import PLANNER_SYSTEM_PROMPT

    test_text = "Q834. Download file. What is the sum of the 'value' column in the table on page 2?"
    try:
        # Test the planner system
        result = await call_llm(PLANNER_SYSTEM_PROMPT, test_text)
        logger.info(f"LLM planner test result: {result[:100]}...")
        return JSONResponse({"status": "success", "llm_response_preview": result[:100]})
    except Exception as e:
        logger.error(f"LLM test failed: {e}")
        return JSONResponse({"status": "error", "message": str(e)})