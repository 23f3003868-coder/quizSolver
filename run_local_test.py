#!/usr/bin/env python3
"""
Script to start the server and run a test
"""
import subprocess
import time
import sys
import os
import signal
import httpx
import json
import asyncio

def start_server():
    """Start the uvicorn server"""
    env = os.environ.copy()
    env['QUIZ_SECRET'] = '495669'
    env['QUIZ_EMAIL'] = '23f3003868@ds.study.iitm.ac.in'
    
    # Start server in background
    process = subprocess.Popen(
        ['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return process

async def test_server():
    """Test the server"""
    print("Waiting for server to start...")
    await asyncio.sleep(5)
    
    service_url = "http://localhost:8000"
    payload = {
        "email": "23f3003868@ds.study.iitm.ac.in",
        "secret": "495669",
        "url": "https://tds-llm-analysis.s-anand.net/project2"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            print(f"\nSending POST request to {service_url}")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            response = await client.post(service_url, json=payload)
            print(f"\nResponse status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                print("\n✅ SUCCESS! Request accepted. Quiz processing started.")
                print("Check the server logs above to see the quiz processing progress.")
                return True
            else:
                print(f"\n❌ Error: Status {response.status_code}")
                return False
    except Exception as e:
        print(f"\n❌ Error testing server: {e}")
        return False

async def main():
    print("=" * 60)
    print("Local Quiz Solver Test")
    print("=" * 60)
    
    # Start server
    print("\nStarting server...")
    server_process = start_server()
    
    try:
        # Test server
        success = await test_server()
        
        if success:
            print("\n" + "=" * 60)
            print("Test completed successfully!")
            print("Server is running. Press Ctrl+C to stop.")
            print("=" * 60)
            print("\nThe quiz is being processed in the background.")
            print("Watch the server output above to see the progress.")
            print("\nTo stop the server, press Ctrl+C")
            
            # Keep server running
            try:
                server_process.wait()
            except KeyboardInterrupt:
                print("\n\nStopping server...")
        else:
            print("\n❌ Test failed")
            server_process.terminate()
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nStopping server...")
        server_process.terminate()
    finally:
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")

if __name__ == "__main__":
    asyncio.run(main())


