# LLM Analysis Quiz Solver

A web service that automatically solves data analysis quizzes by:
- Fetching quiz pages with JavaScript rendering
- Analyzing quiz requirements with LLMs
- Downloading and processing data files (CSV, Excel, PDF)
- Generating and executing code to compute answers
- Submitting responses to quiz endpoints

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

2. Set environment variables:
```bash
export QUIZ_SECRET="your-secret"
export QUIZ_EMAIL="your-email"
export OPENROUTER_API_KEY="sk-..."
```

3. Run the server:
```bash
uvicorn main:app --reload
```

## Usage

Send a POST request to the root endpoint:
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
        "email": "your-email",
        "secret": "your-secret",
        "url": "https://tds-llm-analysis.s-anand.net/demo"
      }'
```

The service will acknowledge the request immediately and process the quiz chain in the background.

## Logging

The application includes comprehensive logging to help with debugging and monitoring:
- Logs capture request details, validation, and processing steps
- Detailed logs for browser operations, data downloads, and LLM interactions
- Error tracking throughout the quiz solving process
- Performance information including timing and resource usage

To increase log verbosity, you can set the LOG_LEVEL environment variable:
```bash
export LOG_LEVEL=DEBUG
```

## Deployment

Deploy to Render using the provided `render.yaml` configuration.