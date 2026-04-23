from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import httpx
import json
import sys

app = FastAPI()
FORWARD_URL = "https://api.apimart.ai/v1/messages"
OUR_API_KEY = "sk-An7bxzzKGHsqNs9b8U4ZGvXfmiL3utujmbPflSro0UUmU9Xu"

client = httpx.AsyncClient(timeout=30.0)

def print_to_terminal(message: str):
    print(message, file=sys.stderr, flush=True)

@app.post("/v1/messages")
async def forward_request(request: Request):
    # 1. 提取用户API Key
    body = await request.json()
    user_api_key = request.headers.get("x-api-key") or request.headers.get("authorization", "").replace("Bearer ", "")
    user_model = body.get("model", "unknown_model")
    print_to_terminal(f"用户API Key: {user_api_key}")
    print_to_terminal(f"用户模型: {user_model}")

    # 2. 准备转发请求
    headers = {
        "Content-Type": "application/json",
        "x-api-key": OUR_API_KEY
    }
    
    # 3. 处理流式/非流式请求
    stream = body.get("stream", False)
    
    if stream:
        async def stream_generator():
            buffer = ""
            input_tokens = 0
            output_tokens = 0
            
            async with client.stream("POST", FORWARD_URL, json=body, headers=headers) as response:
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    # 解析完整的 event: type\ndata: {...} 块
                    while "event: " in buffer and "data: " in buffer:
                        event_start = buffer.find("event: ")
                        data_start = buffer.find("data: ", event_start)
                        if data_start == -1:
                            break
                        
                        # 找到下一个 event 或文件结尾
                        next_event = buffer.find("event: ", data_start + 6)
                        next_newline = buffer.find("\n\n", data_start)
                        
                        if next_newline == -1:
                            break
                        
                        if next_event != -1 and next_event < next_newline:
                            next_newline = next_event - 1
                        
                        event_line = buffer[event_start + 7 : data_start].rstrip("\n")
                        data_content = buffer[data_start + 6 : next_newline].rstrip("\n")
                        buffer = buffer[next_newline + 2:]
                        
                        # 从 message_delta 事件中提取 usage
                        if event_line == "message_delta":
                            try:
                                data = json.loads(data_content)
                                if "usage" in data:
                                    input_tokens = data["usage"].get("input_tokens", 0)
                                    output_tokens = data["usage"].get("output_tokens", 0)
                            except:
                                pass
                    
                    yield chunk
                
                print_to_terminal(f"输入tokens: {input_tokens}, 输出tokens: {output_tokens}")
        
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    
    else:
        response = await client.post(FORWARD_URL, json=body, headers=headers)
        result = response.json()
        
        # 4. 输出tokens消耗 - 直接从顶层获取usage
        if "usage" in result:
            input_tokens = result["usage"].get("input_tokens", 0)
            output_tokens = result["usage"].get("output_tokens", 0)
            print_to_terminal(f"输入tokens: {input_tokens}, 输出tokens: {output_tokens}")
        
        return result

@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()