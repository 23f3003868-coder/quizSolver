import asyncio
import json
from quiz_runner import make_solver_code

async def test_gemini_image_processing():
    # Test with a question that should trigger image processing
    question_summary = "Analyze the chart in the image and determine which category has the highest value"
    page_text = "Look at the attached image showing a bar chart with different categories and their values. Determine which category has the highest value."
    data_descr = "No data files provided"
    html_content = '<html><body><p>Look at the chart</p><img src="https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Cricket_World_Cup_2019_stats.svg/800px-Cricket_World_Cup_2019_stats.svg.png" /></body></html>'
    base_url = "https://example.com"
    
    print("Testing image question processing...")
    print(f"Question: {question_summary}")
    print(f"Base URL: {base_url}")
    
    try:
        # This should trigger the Google Gemini multimodal processing
        result = await make_solver_code(question_summary, page_text, data_descr, html_content, base_url)
        print(f"\nResult code: {result}")
        print("SUCCESS: Image processing was triggered!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_gemini_image_processing())