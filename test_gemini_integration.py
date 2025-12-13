import asyncio
import httpx
import json

async def test_quiz():
    # Send request to your Render service which will solve the quiz
    url = "https://quizsolver-0cy6.onrender.com/solve"

    # Using the provided credentials - the URL in the payload is the quiz to solve
    payload = {
        "email": "23f3003868@ds.study.iitm.ac.in",
        "secret": "495669",
        "url": "https://p2testingone.vercel.app/q1.html"
    }
    
    print(f"Sending POST request to: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=payload)
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"Response Content: {response.text}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"Parsed JSON Response: {json.dumps(result, indent=2)}")
                except:
                    print("Could not parse response as JSON")
            else:
                print(f"Request failed with status {response.status_code}")
                
    except Exception as e:
        print(f"Error making request: {e}")

if __name__ == "__main__":
    asyncio.run(test_quiz())