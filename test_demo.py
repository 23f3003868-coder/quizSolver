#!/usr/bin/env python3
"""
Test script to verify the demo quiz functionality
"""
import asyncio
import json
import httpx
from pprint import pprint

async def test_demo_quiz():
    print("Testing demo quiz page...")
    
    # Test the demo page
    async with httpx.AsyncClient() as client:
        try:
            # Get the demo page
            response = await client.get("http://localhost:10000/demo")
            print(f"\nDemo page status: {response.status_code}")
            print(f"Demo page length: {len(response.text)}")
            
            # Check if we can access the CSV data
            csv_response = await client.get("http://localhost:10000/data/quiz-data.csv")
            print(f"\nCSV data status: {csv_response.status_code}")
            print(f"CSV content:\n{csv_response.text}")
            
            # Test the quiz solver with the demo URL
            payload = {
                "email": "23f3003868@ds.study.iitm.ac.in",
                "secret": "495669", 
                "url": "http://localhost:10000/demo"
            }
            
            print(f"\nSending quiz solve request: {json.dumps(payload, indent=2)}")
            solve_response = await client.post("http://localhost:10000/", json=payload)
            print(f"\nQuiz solve request status: {solve_response.status_code}")
            print(f"Response: {solve_response.text}")
            
        except Exception as e:
            print(f"Error during testing: {e}")

if __name__ == "__main__":
    asyncio.run(test_demo_quiz())