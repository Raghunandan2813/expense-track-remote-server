import sys
import httpx
import asyncio
import json

# Your actual live URL
URL = "https://recent-black-jay.fastmcp.app/sse?token=my-secret-key-123"

async def main():
    headers = {"Accept": "text/event-stream"}
    # Use a longer timeout for the initial connection
    timeout = httpx.Timeout(10.0, read=None)
    
    print(f"Connecting to {URL}...", file=sys.stderr)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("GET", URL, headers=headers) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    print(f"Error: Server returned status {response.status_code}", file=sys.stderr)
                    print(f"Server Message: {body.decode()}", file=sys.stderr)
                    return


                print("Connected! Listening for messages...", file=sys.stderr)
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        # Pass JSON data to Claude
                        sys.stdout.write(line[6:] + "\n")
                        sys.stdout.flush()
    except Exception as e:
        print(f"Bridge Exception: {type(e).__name__}: {e}", file=sys.stderr)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal Error: {e}", file=sys.stderr)

