import sys
import httpx
import asyncio
import json
import os

# Your actual live URL
BASE_URL = "https://expense-track-remote-server.onrender.com"
URL = f"{BASE_URL}/sse?token=my-secret-key-123"

async def stdio_to_sse(client, post_url):
    """Read from stdin (Claude) and POST to the server."""
    loop = asyncio.get_event_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        try:
            payload = json.loads(line)
            await client.post(post_url, json=payload)
        except Exception as e:
            print(f"Post Error: {e}", file=sys.stderr)

async def main():
    headers = {"Accept": "text/event-stream"}
    timeout = httpx.Timeout(10.0, read=None)
    
    print(f"Connecting to {URL}...", file=sys.stderr)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream("GET", URL, headers=headers) as response:
                if response.status_code != 200:
                    print(f"Error: Status {response.status_code}", file=sys.stderr)
                    return

                # Use a single iterator for the whole stream
                lines = response.aiter_lines()
                
                # 1. Find the endpoint
                post_url = None
                async for line in lines:
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data.startswith("/") or data.startswith("http"):
                            post_url = f"{BASE_URL}{data}" if data.startswith("/") else data
                            break
                    elif line.startswith("/") or line.startswith("http"):
                        post_url = f"{BASE_URL}{line}" if line.startswith("/") else line
                        break
                
                if not post_url:
                    print("Error: Could not find endpoint", file=sys.stderr)
                    return

                print(f"Connected! Bridge active.", file=sys.stderr)
                
                # 2. Start handling Claude's requests
                asyncio.create_task(stdio_to_sse(client, post_url))

                # 3. Handle messages FROM the server TO Claude (continue with the SAME iterator)
                async for line in lines:
                    if line.startswith("data: "):
                        sys.stdout.write(line[6:] + "\n")
                        sys.stdout.flush()

        except Exception as e:
            print(f"Bridge Exception: {e}", file=sys.stderr)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


