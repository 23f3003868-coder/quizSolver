#!/usr/bin/env python3
"""
Test script to send a POST request to the deployed quiz solver service with the correct demo URL
"""
import asyncio
import json
import httpx
from pprint import pprint

async def test_quiz_solver():
    print("Testing deployed quiz solver service with actual demo quiz...")
    
    # Define the service URL
    service_url = "https://quizsolver-0cy6.onrender.com"
    
    # Define the payload for the actual demo quiz from the assignment
    payload = {
        "email": "23f3003868@ds.study.iitm.ac.in",
        "secret": "495669", 
        "url": "https://tds-llm-analysis.s-anand.net/demo"  # This is the actual demo from the assignment
    }
    
    print(f"Sending request to: {service_url}")
    print(f"With payload: {json.dumps(payload, indent=2)}")
    
    async with httpx.AsyncClient(timeout=120) as client:  # Increased timeout to 2 minutes
        try:
            print("Making request...")
            response = await client.post(service_url, json=payload)
            print(f"\nResponse status: {response.status_code}")
            print(f"Response body: {response.text}")

            if response.status_code == 200:
                print("\n✅ Request successful! The quiz solver should now process the demo quiz in the background.")
            elif response.status_code == 403:
                print("\n❌ Forbidden - likely incorrect email or secret")
            elif response.status_code == 400:
                print("\n❌ Bad request - likely invalid JSON or missing fields")
            else:
                print(f"\n⚠️  Unexpected status code: {response.status_code}")

        except httpx.TimeoutException as e:
            print(f"Request timed out: {e}")
        except httpx.RequestError as e:
            print(f"Request failed: {e}")
        except Exception as e:
            print(f"Error occurred: {e}")

async def check_quiz_status():
    """Check if the quiz was processed by attempting to access the quiz URL directly"""
    print("\nChecking quiz URL to see if it's accessible...")

    quiz_url = "https://tds-llm-analysis.s-anand.net/demo"

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(quiz_url)
            print(f"Quiz URL status: {response.status_code}")
            if response.status_code == 200:
                print("✅ Quiz URL is accessible - content loaded successfully")
                # Look for some specific content to verify it's the right page
                if "quiz" in response.text.lower() or "data" in response.text.lower():
                    print("✅ Confirmed the page contains quiz-related content")
            else:
                print(f"❌ Quiz URL returned status: {response.status_code}")
        except Exception as e:
            print(f"Error accessing quiz URL: {e}")

if __name__ == "__main__":
    asyncio.run(test_quiz_solver())
    asyncio.run(check_quiz_status())