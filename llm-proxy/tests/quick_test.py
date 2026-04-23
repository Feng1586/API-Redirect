#!/usr/bin/env python3
import subprocess
import time
import signal
import sys
import os
import httpx
import asyncio

def start_server():
    """启动Gemini API代理服务"""
    print("启动Gemini API代理服务...")
    
    # 使用subprocess启动服务
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "test_gemini_api:app", 
         "--host", "127.0.0.1", "--port", "8000", "--reload"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # 等待服务启动
    print("等待服务启动...")
    for _ in range(30):  # 最多等待30秒
        try:
            response = httpx.get("http://127.0.0.1:8000/", timeout=2)
            if response.status_code == 200:
                print("服务启动成功！")
                return process
        except:
            time.sleep(1)
            continue
    
    print("服务启动失败")
    return process

def stop_server(process):
    """停止服务"""
    print("\n停止服务...")
    process.terminate()
    process.wait(timeout=5)
    print("服务已停止")

async def test_health():
    """测试健康检查"""
    print("\n1. 测试健康检查...")
    try:
        response = httpx.get("http://127.0.0.1:8000/", timeout=5)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        return True
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False

async def test_non_stream():
    """测试非流式请求"""
    print("\n2. 测试非流式请求...")
    
    url = "http://127.0.0.1:8000/v1beta/models/gemini-2.0-flash-exp:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-api-key"
    }
    
    body = {
        "contents": [{
            "parts": [{
                "text": "你好，请简单介绍一下自己"
            }]
        }],
        "generationConfig": {
            "maxOutputTokens": 50
        }
    }
    
    try:
        response = await httpx.AsyncClient(timeout=30.0).post(url, json=body, headers=headers)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"请求成功！")
            
            # 检查响应结构
            if "candidates" in result:
                print(f"找到 {len(result['candidates'])} 个候选")
                if len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                print(f"响应文本: {part['text'][:100]}...")
            
            if "usageMetadata" in result:
                usage = result["usageMetadata"]
                print(f"使用统计 - Prompt: {usage.get('promptTokenCount', 0)}, Candidates: {usage.get('candidatesTokenCount', 0)}")
            return True
        else:
            print(f"请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"非流式请求异常: {e}")
        return False

async def test_stream():
    """测试流式请求"""
    print("\n3. 测试流式请求...")
    
    url = "http://127.0.0.1:8000/v1beta/models/gemini-2.0-flash-exp:streamGenerateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-api-key"
    }
    
    body = {
        "contents": [{
            "parts": [{
                "text": "用中文写一个简短的Python程序"
            }]
        }],
        "generationConfig": {
            "maxOutputTokens": 100
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=body, headers=headers) as response:
                print(f"状态码: {response.status_code}")
                print(f"Content-Type: {response.headers.get('content-type')}")
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    print(f"错误: {error_text.decode()}")
                    return False
                
                print("开始接收流式数据...")
                chunk_count = 0
                total_text = ""
                
                async for chunk in response.aiter_bytes():
                    chunk_str = chunk.decode('utf-8')
                    
                    # 处理SSE格式
                    lines = chunk_str.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                print("收到结束信号 [DONE]")
                            else:
                                chunk_count += 1
                                if chunk_count <= 3:  # 只显示前3个chunk
                                    print(f"Chunk {chunk_count}: {data[:100]}...")
                                elif chunk_count == 4:
                                    print("... (更多chunk)")
                                try:
                                    data_json = httpx._decoders.json_decoder(data)
                                    # 尝试提取文本
                                    if "candidates" in data_json and len(data_json["candidates"]) > 0:
                                        candidate = data_json["candidates"][0]
                                        if "content" in candidate and "parts" in candidate["content"]:
                                            for part in candidate["content"]["parts"]:
                                                if "text" in part:
                                                    total_text += part["text"]
                                except:
                                    pass
                
                print(f"\n流式传输完成 - 共收到 {chunk_count} 个chunk")
                print(f"总文本长度: {len(total_text)} 字符")
                if total_text:
                    print(f"前200字符: {total_text[:200]}...")
                return True
    except Exception as e:
        print(f"流式请求异常: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("=" * 50)
    print("Gemini API代理测试")
    print("=" * 50)
    
    # 检查文件
    if not os.path.exists("test_gemini_api.py"):
        print("错误: test_gemini_api.py 不存在")
        return 1
    
    # 启动服务
    server_process = start_server()
    if server_process is None:
        return 1
    
    try:
        # 等待服务完全启动
        await asyncio.sleep(3)
        
        # 运行测试
        tests_passed = 0
        total_tests = 3
        
        if await test_health():
            tests_passed += 1
        
        if await test_non_stream():
            tests_passed += 1
        
        if await test_stream():
            tests_passed += 1
        
        # 输出结果
        print("\n" + "=" * 50)
        print(f"测试结果: {tests_passed}/{total_tests} 通过")
        print("=" * 50)
        
        return 0 if tests_passed == total_tests else 1
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        return 1
    except Exception as e:
        print(f"\n测试发生异常: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        stop_server(server_process)

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)