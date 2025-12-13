# LLM Analysis Quiz Solver

A web service that automatically solves data analysis quizzes using an autonomous agent architecture with modular tools.

## Features

- 🤖 **Autonomous Agent**: LangGraph-inspired agent architecture for deterministic tool routing
- 🔍 **Web Scraping**: Playwright-based JavaScript rendering for dynamic quiz pages
- 📥 **Data Processing**: Download and process CSV, Excel, PDF, and JSON files
- 🧮 **Code Generation**: LLM-powered Python code generation for data analysis
- 📊 **Data Visualization**: Generate summaries and insights from loaded data
- 🔗 **Quiz Chain Navigation**: Automatically navigate through multi-step quiz chains

## Architecture

The solver uses a modular tool-based architecture:

- **Agent** (`agent.py`): Orchestrates the quiz-solving workflow
- **Tools** (`tools/`): Modular tools for scraping, downloading, computing, and visualizing
  - `scrape_tool.py`: Web page scraping with Playwright
  - `download_tool.py`: File downloading and loading
  - `compute_tool.py`: LLM-powered answer computation
  - `visualize_tool.py`: Data summarization and visualization
- **Gemini Client** (`gemini_client.py`): Google Gemini API integration
- **FastAPI Server** (`main.py`): REST API endpoints

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

2. Set environment variables:
```bash
export GOOGLE_API_KEY="your_gemini_api_key"
```

3. Run the server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### POST `/solve`

Triggers the autonomous quiz solver.

**Request:**
```json
{
  "email": "your_email@ds.study.iitm.ac.in",
  "secret": "your_secret",
  "url": "https://tds-llm-analysis.s-anand.net/demo"
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Processing started"
}
```

### GET `/healthz`

Health check endpoint for monitoring services.

**Response:**
```json
{
  "status": "ok",
  "uptime_seconds": 120
}
```

## Usage

Send a POST request to the `/solve` endpoint:
```bash
curl -X POST http://localhost:8000/solve \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your_email@ds.study.iitm.ac.in",
    "secret": "your_secret",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
```

The service will acknowledge the request immediately and process the quiz chain in the background.

## How the Agent Works

1. **Fetch quiz page** (Playwright) - Renders JavaScript and extracts content
2. **Extract instructions + data** - Analyzes page to identify requirements
3. **Analyze instructions** (Gemini LLM) - Determines what needs to be done
4. **Decide tool to call**:
   - 🔍 Scrape web pages
   - 📥 Download files
   - 📊 Visualize data
   - 🔢 Compute results
5. **Generate & execute Python code** - LLM generates code, agent executes it
6. **Format answer JSON** - Prepares submission payload
7. **Submit answer** - POSTs to quiz endpoint
8. **Read evaluator response** - Checks for correctness and next URL
9. **Navigate quiz chain** - Repeats until completion

## Deployment

### Docker

Build and run with Docker:
```bash
docker build -t quiz-solver .
docker run -p 10000:10000 -e GOOGLE_API_KEY=your_key quiz-solver
```

### Render

Deploy to Render using the provided `render.yaml` configuration. The service will:
- Automatically install dependencies
- Install Playwright browsers
- Start the FastAPI server on port 10000

## Logging

The application includes comprehensive logging:
- Request details and validation
- Browser operations and page scraping
- Data downloads and processing
- LLM interactions and code generation
- Error tracking throughout the process

Set log level:
```bash
export LOG_LEVEL=DEBUG
```

## Requirements

- Python 3.11+
- FastAPI
- Playwright (Chromium)
- Google Gemini API key
- Pandas, PDFPlumber for data processing