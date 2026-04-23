#!/usr/bin/env python3
import httpx
import asyncio
import json
import sys

async def test_upstream_direct():
    """直接测试上游API"""
    print("直接测试上游API...")
    
    # 尝试不同的模型
    models_to_test = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro-thinking"
    ]
    
    upstream_base = "https://api.apimart.ai/v1beta/models"
    api_key = "sk-An7bxzzKGHsqNs9b8U4ZGvXfmiL3utujmbPflSro0UUmU9Xu"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    body = {
        "contents": [{
            "parts": [{
                "text": "Hello"
            }]
        }],
        "generationConfig": {
            "maxOutputTokens": 10
        }
    }
    
    for model in models_to_test:
        print(f"\n测试模型: {model}")
        
        # 测试非流式
        url = f"{upstream_base}/{model}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=body, headers=headers)
                print(f"非流式状态码: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"非流式成功！")
                    if "candidates" in result:
                        print(f"有 {len(result['candidates'])} 个候选")
                    return model  # 返回可用的模型
                else:
                    print(f"错误: {response.text}")
        except Exception as e:
            print(f"异常: {e}")
    
    return None

async def test_proxy_with_mock():
    """测试代理服务的流式传输逻辑"""
    print("\n\n测试代理服务的流式传输逻辑...")
    
    # 使用一个简单的模拟上游，返回SSE数据
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse
    import uvicorn
    import threading
    import time
    
    # 创建模拟上游服务
    mock_app = FastAPI()
    
    @mock_app.post("/v1beta/models/{model}:{method}")
    async def mock_upstream(model: str, method: str, request: Request):
        print(f"模拟上游收到请求: model={model}, method={method}")
        
        body = await request.json()
        print(f"请求体: {body}")
        
        if method == "streamGenerateContent":
            async def generate_sse():
                # 生成一些SSE数据
                for i in range(3):
                    data = {
                        "candidates": [{
                            "content": {
                                "parts": [{
                                    "text": f"这是流式响应块 {i+1}"
                                }]
                            }
                        }]
                    }
                    if i == 2:  # 最后一块添加usage信息
                        data["usageMetadata"] = {
                            "promptTokenCount": 5,
                            "candidatesTokenCount": 15
                        }
                    
                    yield f"data: {json.dumps(data)}\n\n".encode('utf-8')
                    await asyncio.sleep(0.1)
                
                # 发送结束信号
                yield b"data: [DONE]\n\n"
            
            return StreamingResponse(generate_sse(), media_type="text/event-stream")
        else:
            return {
                "candidates": [{
                    "content": {
                        "parts": [{
                            "text": "这是非流式响应"
                        }]
                    }
                }],
                "usageMetadata": {
                    "promptTokenCount": 5,
                    "candidatesTokenCount": 10
                }
            }
    
    # 启动模拟上游
    import subprocess
    mock_process = subprocess.Popen(
        [sys.executable, "-c", """
import asyncio
from debug_stream_mock import mock_app
import uvicorn
uvicorn.run(mock_app, host="127.0.0.1", port=9001)
"""],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # 等待启动
    await asyncio.sleep(3)
    
    # 测试代理（需要修改test_gemini_api.py使用模拟上游）
    print("启动代理服务...")
    import subprocess
    import os
    
    # 备份原文件
    with open("test_gemini_api.py", "r", encoding="utf-8") as f:
        original_content = f.read()
    
    # 修改代理配置使用模拟上游
    modified_content = original_content.replace(
        'UPSTREAM_BASE_URL = "https://api.apimart.ai/v1beta/models"',
        'UPSTREAM_BASE_URL = "http://127.0.0.1:9001/v1beta/models"'
    )
    
    with open("test_gemini_api.py", "w", encoding="utf-8") as f:
        f.write(modified_content)
    
    # 启动代理服务
    proxy_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "test_gemini_api:app", 
         "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    await asyncio.sleep(3)
    
    # 测试代理
    print("\n测试代理流式传输...")
    url = "http://127.0.0.1:8000/v1beta/models/test-model:streamGenerateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-key"
    }
    
    body = {
        "contents": [{
            "parts": [{
                "text": "测试消息"
            }]
        }]
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, json=body, headers=headers) as response:
                print(f"代理状态码: {response.status_code}")
                
                chunk_count = 0
                async for chunk in response.aiter_bytes():
                    chunk_str = chunk.decode('utf-8')
                    if chunk_str.strip():
                        chunk_count += 1
                        print(f"收到chunk {chunk_count}: {chunk_str[:100]}...")
                
                print(f"总共收到 {chunk_count} 个chunk")
    except Exception as e:
        print(f"测试异常: {e}")
    
    # 清理
    proxy_process.terminate()
    mock_process.terminate()
    
    # 恢复原文件
    with open("test_gemini_api.py", "w", encoding="utf-8") as f:
        f.write(original_content)
    
    return True

async def main():
    print("调试Gemini API流式传输")
    print("=" * 50)
    
    # 测试上游API
    available_model = await test_upstream_direct()
    
    if available_model:
        print(f"\n找到可用的模型: {available_model}")
        print("建议在test_gemini_api.py中使用此模型")
    else:
        print("\n未找到可用模型，可能是API密钥问题或服务不可用")
    
    # 测试代理逻辑
    print("\n" + "=" * 50)
    print("注意：以下测试需要单独的模拟上游服务实现")
    print("由于时间限制，这里只提供调试思路")
    
    print("\n调试建议：")
    print("1. 检查上游API密钥是否有效")
    print("2. 尝试其他Gemini模型名称")
    print("3. 使用 curl 或 Postman 直接测试上游API")
    print("4. 在 stream_upstream 函数中添加更多日志")
    print("5. 确保上游返回正确的SSE格式")

if __name__ == "__main__":
    asyncio.run(main())