from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import json
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPSTREAM_URL = "https://api.apimart.ai/v1/responses"
OUR_API_KEY = "sk-An7bxzzKGHsqNs9b8U4ZGvXfmiL3utujmbPflSro0UUmU9Xu"

@app.post("/v1/responses")
async def proxy_responses(request: Request):
    # 提取用户API Key
    auth_header = request.headers.get("authorization", "")
    x_api_key = request.headers.get("x_api_key", "")
    
    user_api_key = ""
    if auth_header.startswith("Bearer "):
        user_api_key = auth_header[7:]
    elif x_api_key:
        user_api_key = x_api_key
    
    logger.info(f"User API Key: {user_api_key}")
    
    # 解析请求体
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # 提取模型名称
    model = body.get("model", "")
    logger.info(f"Model: {model}")
    
    # 检查是否为流式请求
    stream = body.get("stream", False)
    
    # 替换API Key
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OUR_API_KEY}"
    }
    
    # 转发请求
    if stream:
        return await handle_stream_request(headers, body)
    else:
        return await handle_normal_request(headers, body)

async def handle_normal_request(headers: dict, body: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            UPSTREAM_URL,
            json=body,
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )
        
        result = response.json()
        
        # 统计tokens
        if "usage" in result:
            usage = result["usage"]
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            logger.info(f"Input tokens: {input_tokens}")
            logger.info(f"Output tokens: {output_tokens}")
        
        return result

async def handle_stream_request(headers: dict, body: dict):
    input_tokens = 0
    output_tokens = 0
    
    async def generate():
        nonlocal input_tokens, output_tokens
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers["Accept"] = "text/event-stream"
            async with client.stream(
                "POST",
                UPSTREAM_URL,
                json=body,
                headers=headers
            ) as upstream:
                async for line in upstream.aiter_lines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    
                    if stripped.startswith("data: "):
                        data_str = stripped[6:]
                        if data_str == "[DONE]":
                            # 流结束时输出统计
                            logger.info(f"Stream completed - Input tokens: {input_tokens}, Output tokens: {output_tokens}")
                            yield b"data: [DONE]\n\n"
                            continue
                        
                        try:
                            data = json.loads(data_str)
                            # 检查是否为完成事件，usage嵌套在response对象中
                            if data.get("type") == "response.completed":
                                response_data = data.get("response", {})
                                usage = response_data.get("usage")
                                if usage:
                                    input_tokens = usage.get("input_tokens", 0)
                                    output_tokens = usage.get("output_tokens", 0)
                                    logger.info(f"Stream completed - Input tokens: {input_tokens}, Output tokens: {output_tokens}")
                        except json.JSONDecodeError:
                            pass
                        
                        yield f"data: {data_str}\n\n".encode("utf-8")
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )