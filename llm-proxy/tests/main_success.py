from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, Response
import httpx
import os
import json

app = FastAPI()

OPENAI_API_KEY = "sk-An7bxzzKGHsqNs9b8U4ZGvXfmiL3utujmbPflSro0UUmU9Xu"
TARGET_BASE_URL = "https://api.apimart.ai/v1"

ALLOWED_HEADERS = {
    "content-type", "accept", "user-agent",
    "x-request-id", "openai-organization"
}

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    
    url = f"{TARGET_BASE_URL}/chat/completions"
    
    headers = {}
    for key, value in request.headers.items():
        if key.lower() in ALLOWED_HEADERS:
            headers[key] = value
    headers["Content-Type"] = "application/json"
    headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
    
    body = await request.body()
    body_json = json.loads(body)
    client_stream = body_json.get("stream")  # None/True/False
    
    return StreamingResponse(
        stream_with_usage_logging("POST", url, headers, body, client_stream),
        media_type="text/event-stream"
    )


async def stream_with_usage_logging(method, url, headers, body, client_stream):
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        
        # 客户端要求流式 或 未指定 → 上游请求流式
        if client_stream is True or client_stream is None:
            headers["Accept"] = "text/event-stream"
            
            async with client.stream(method, url, headers=headers, content=body) as upstream:
                async for line in upstream.aiter_lines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if stripped.startswith('data: '):
                        data_str = stripped[6:]
                        if data_str == '[DONE]':
                            yield b'data: [DONE]\n\n'
                            continue
                        try:
                            data = json.loads(data_str)
                            if "usage" in data and data["usage"]:
                                print_usage(data["usage"])
                        except json.JSONDecodeError:
                            pass
                        yield f"data: {data_str}\n\n".encode('utf-8')
        
        # 客户端要求非流式 → 上游请求非流式
        else:
            upstream = await client.post(url, headers=headers, content=body)
            response_data = upstream.json()
            if "usage" in response_data:
                print_usage(response_data["usage"])
            
            yield upstream.content  # 直接透传原始响应

def print_usage(usage):
    print(f"\n{'='*50}")
    print(f"Prompt Tokens:     {usage['prompt_tokens']}")
    print(f"Completion Tokens: {usage['completion_tokens']}")
    print(f"Total Tokens:      {usage['total_tokens']}")
    print(f"{'='*50}\n")