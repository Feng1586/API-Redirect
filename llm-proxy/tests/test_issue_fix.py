#!/usr/bin/env python3
import subprocess
import time
import sys
import os
import httpx
import asyncio
import json

def start_server():
    """启动服务"""
    print("启动服务...")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "test_gemini_api:app", 
         "--host", "127.0.0.1", "--port", "8000", "--reload"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # 等待启动
    for _ in range(30):
        try:
            response = httpx.get("http://127.0.0.1:8000/", timeout=2)
            if response.status_code == 200:
                print("服务启动成功")
                return process
        except:
            time.sleep(1)
    
    print("服务启动失败")
    return process

def stop_server(process):
    """停止服务"""
    print("\n停止服务...")
    process.terminate()
    process.wait(timeout=5)

async def test_upstream_direct():
    """直接测试上游API，查看流式和非流式响应的区别"""
    print("\n=== 直接测试上游API ===")
    
    upstream_base = "https://api.apimart.ai/v1beta/models"
    api_key = "sk-An7bxzzKGHsqNs9b8U4ZGvXfmiL3utujmbPflSro0UUmU9Xu"
    model = "gemini-2.5-flash"
    
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
            "maxOutputTokens": 50
        }
    }
    
    # 测试非流式
    print("1. 测试非流式 (generateContent)...")
    url = f"{upstream_base}/{model}:generateContent"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=body, headers=headers)
            print(f"状态码: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"响应长度: {len(response.text)} 字符")
            
            if response.status_code == 200:
                # 检查响应结构
                try:
                    result = response.json()
                    print(f"响应类型: JSON")
                    if "candidates" in result:
                        print(f"有 {len(result['candidates'])} 个候选")
                except:
                    print(f"响应可能不是JSON")
        except Exception as e:
            print(f"非流式测试异常: {e}")
    
    # 测试流式（不加alt=sse参数）
    print("\n2. 测试流式 (streamGenerateContent) - 不加alt参数...")
    url = f"{upstream_base}/{model}:streamGenerateContent"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            async with client.stream("POST", url, json=body, headers=headers) as response:
                print(f"状态码: {response.status_code}")
                print(f"Content-Type: {response.headers.get('content-type')}")
                
                # 读取前几行看看
                lines_collected = []
                async for line in response.aiter_lines():
                    if line.strip():
                        lines_collected.append(line)
                        if len(lines_collected) >= 3:
                            break
                
                print(f"前3行响应:")
                for i, line in enumerate(lines_collected[:3]):
                    print(f"  {i+1}: {line[:200]}")
                    
                if len(lines_collected) > 0:
                    first_line = lines_collected[0]
                    if first_line.startswith('{'):
                        print("结论: 上游返回JSON格式，不是SSE")
                    elif 'data:' in first_line.lower():
                        print("结论: 上游返回SSE格式")
                    else:
                        print(f"结论: 未知格式: {first_line[:100]}")
        except Exception as e:
            print(f"流式测试异常: {e}")
    
    # 测试流式（加alt=sse参数）
    print("\n3. 测试流式 (streamGenerateContent) - 加alt=sse参数...")
    url = f"{upstream_base}/{model}:streamGenerateContent?alt=sse"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            async with client.stream("POST", url, json=body, headers=headers) as response:
                print(f"状态码: {response.status_code}")
                print(f"Content-Type: {response.headers.get('content-type')}")
                
                # 读取前几行看看
                lines_collected = []
                async for line in response.aiter_lines():
                    if line.strip():
                        lines_collected.append(line)
                        if len(lines_collected) >= 3:
                            break
                
                print(f"前3行响应:")
                for i, line in enumerate(lines_collected[:3]):
                    print(f"  {i+1}: {line[:200]}")
                    
                if len(lines_collected) > 0:
                    first_line = lines_collected[0]
                    if first_line.startswith('{'):
                        print("结论: 上游返回JSON格式，不是SSE")
                    elif 'data:' in first_line.lower():
                        print("结论: 上游返回SSE格式")
                    else:
                        print(f"结论: 未知格式: {first_line[:100]}")
        except Exception as e:
            print(f"流式测试异常: {e}")

async def test_proxy_fix():
    """测试修复后的代理"""
    print("\n=== 测试代理修复 ===")
    
    # 启动代理服务
    server_process = start_server()
    if server_process is None:
        return
    
    try:
        await asyncio.sleep(3)
        
        # 测试代理流式端点
        print("测试代理流式端点...")
        url = "http://127.0.0.1:8000/v1beta/models/gemini-2.5-flash:streamGenerateContent"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-key"
        }
        
        body = {
            "contents": [{
                "parts": [{
                    "text": "Hello, this is a test"
                }]
            }],
            "generationConfig": {
                "maxOutputTokens": 50
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                async with client.stream("POST", url, json=body, headers=headers) as response:
                    print(f"代理状态码: {response.status_code}")
                    print(f"代理Content-Type: {response.headers.get('content-type')}")
                    
                    # 收集响应
                    chunks = []
                    async for chunk in response.aiter_bytes():
                        chunks.append(chunk)
                    
                    full_response = b''.join(chunks).decode('utf-8')
                    print(f"响应总长度: {len(full_response)} 字符")
                    
                    # 分析响应格式
                    lines = full_response.split('\n')
                    data_lines = [line for line in lines if line.startswith('data: ')]
                    
                    print(f"找到 {len(data_lines)} 个data行")
                    
                    if data_lines:
                        for i, line in enumerate(data_lines[:2]):  # 显示前2个
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                print(f"  Data {i+1}: [DONE]")
                            else:
                                print(f"  Data {i+1}: {data_str[:100]}...")
                                
                                try:
                                    data_json = json.loads(data_str)
                                    if "candidates" in data_json:
                                        print(f"    包含candidates字段")
                                    if "usageMetadata" in data_json:
                                        print(f"    包含usageMetadata字段")
                                except:
                                    print(f"    不是有效JSON")
                    
                    # 检查是否有[DONE]
                    if '[DONE]' in full_response:
                        print("响应包含[DONE]信号")
                    else:
                        print("警告: 响应缺少[DONE]信号")
                        
            except Exception as e:
                print(f"代理测试异常: {e}")
                import traceback
                traceback.print_exc()
    finally:
        stop_server(server_process)

async def analyze_issue():
    """分析问题"""
    print("\n=== 问题分析 ===")
    print("从日志可以看出:")
    print("1. 上游API返回的Content-Type是 'application/json; charset=UTF-8'")
    print("2. 响应是完整的JSON对象，不是SSE流")
    print("3. 这意味着上游API可能不支持真正的流式传输")
    print("4. 或者请求参数不正确（缺少alt=sse）")
    print("5. 或者上游API只支持非流式模式")
    
    print("\n解决方案:")
    print("1. 如果上游不支持流式，代理应该将JSON响应包装成SSE格式")
    print("2. 添加alt=sse参数到上游请求")
    print("3. 修改代理逻辑，根据上游响应类型进行适配")

async def main():
    """主函数"""
    print("分析Gemini API流式传输问题")
    print("=" * 60)
    
    # 分析问题
    await analyze_issue()
    
    # 直接测试上游API
    await test_upstream_direct()
    
    # 测试代理修复
    await test_proxy_fix()
    
    print("\n" + "=" * 60)
    print("测试完成")

if __name__ == "__main__":
    asyncio.run(main())