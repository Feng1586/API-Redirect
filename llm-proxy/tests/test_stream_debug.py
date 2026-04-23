import httpx
import asyncio
import sys

FORWARD_URL = "http://127.0.0.1:8000/api/v1/messages"
OUR_API_KEY = "sk-qtaj1dixte6rc5mr3sxod149wpoke315"

async def test_stream():
    body = {
        "model": "claude-haiku-4-5-20251001",
        "messages": [{"role": "user", "content": "你好"}],
        "stream": False
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": OUR_API_KEY
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", FORWARD_URL, json=body, headers=headers) as response:
            print(f"状态码: {response.status_code}", file=sys.stderr)
            async for chunk in response.aiter_text():
                if chunk.strip():
                    print(f"原始chunk: {repr(chunk)}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(test_stream())
