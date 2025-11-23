#!/usr/bin/env python3
"""
Test script to send a POST request to the submit endpoint directly
"""
import asyncio
import json
import httpx
from pprint import pprint

async def test_submit_endpoint():
    print("Testing submit endpoint directly...")
    
    # Define the service URL
    service_url = "https://quizsolver-0cy6.onrender.com"
    
    # Define the payload for submitting an answer (as would be sent by the system)
    payload = {
        "email": "23f3003868@ds.study.iitm.ac.in",
        "secret": "495669", 
        "url": "https://quizsolver-0cy6.onrender.com/demo",
        "answer": 30  # The correct answer (average of [10,20,30,40,50])
    }
    
    print(f"Sending POST request to: {service_url}/submit")
    print(f"With payload: {json.dumps(payload, indent=2)}")
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(f"{service_url}/submit", json=payload)
            print(f"\nResponse status: {response.status_code}")
            print(f"Response body: {response.text}")
            
            if response.status_code == 200:
                print("\n✅ Submit endpoint accepted the answer!")
                response_data = response.json()
                print(f"Response data: {response_data}")
                
                if response_data.get("correct"):
                    print(f"✅ Answer was correct! Reason: {response_data.get('reason')}")
                else:
                    print(f"❌ Answer was incorrect. Reason: {response_data.get('reason')}")
            else:
                print(f"\n⚠️  Unexpected status code: {response.status_code}")
                
        except httpx.RequestError as e:
            print(f"Request failed: {e}")
        except Exception as e:
            print(f"Error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_submit_endpoint())