#!/usr/bin/env python3
"""
Test script to send a POST request to the deployed quiz solver service
"""
import asyncio
import json
import httpx
from pprint import pprint

async def test_quiz_solver():
    print("Testing deployed quiz solver service...")
    
    # Define the service URL
    service_url = "https://quizsolver-0cy6.onrender.com"
    endpoint = f"{service_url}/solve"
    
    # Define the payload for the demo quiz
    payload = {
        "email": "23f3003868@ds.study.iitm.ac.in",
        "secret": "495669", 
        "url": f"{service_url}/demo"  # Using the demo endpoint on the same service
    }
    
    print(f"Sending request to: {endpoint}")
    print(f"With payload: {json.dumps(payload, indent=2)}")
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(endpoint, json=payload)
            print(f"\nResponse status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            print(f"Response body: {response.text}")
            
            if response.status_code == 200:
                print("\n✅ Request successful! The quiz solver should now process the demo quiz in the background.")
            elif response.status_code == 403:
                print("\n❌ Forbidden - likely incorrect email or secret")
            elif response.status_code == 400:
                print("\n❌ Bad request - likely invalid JSON or missing fields")
            else:
                print(f"\n⚠️  Unexpected status code: {response.status_code}")
                
        except httpx.RequestError as e:
            print(f"Request failed: {e}")
        except Exception as e:
            print(f"Error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_quiz_solver())