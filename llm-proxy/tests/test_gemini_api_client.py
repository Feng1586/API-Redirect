import httpx
import asyncio
import json
import sys
from typing import AsyncGenerator

# 测试配置
BASE_URL = "http://127.0.0.1:8000/api/v1/beta/models"  # 本地测试地址
TEST_API_KEY = "sk-qtaj1dixte6rc5mr3sxod149wpoke315"  # 测试用的API密钥
MODEL = "gemini-2.5-flash"  # 根据调试结果，使用可用的模型

async def test_non_streaming():
    """测试非流式传输"""
    print("=== 测试非流式传输 ===")
    
    url = f"{BASE_URL}/{MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_API_KEY}"
    }
    
    body = {
        "contents": [{
            "parts": [{
                "text": "请用中文简要介绍Python编程语言"
            }]
        }],
        "generationConfig": {
            "maxOutputTokens": 100
        }
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=body, headers=headers)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"响应类型: {type(result)}")
                print(f"响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
                
                # 检查是否有usageMetadata
                if "usageMetadata" in result:
                    usage = result["usageMetadata"]
                    print(f"Prompt tokens: {usage.get('promptTokenCount', 0)}")
                    print(f"Candidates tokens: {usage.get('candidatesTokenCount', 0)}")
                
                # 提取响应文本
                if "candidates" in result and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                print(f"\n生成的文本: {part['text']}")
            else:
                print(f"错误: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"请求异常: {e}")

async def test_streaming():
    """测试流式传输"""
    print("\n=== 测试流式传输 ===")
    
    url = f"{BASE_URL}/{MODEL}:streamGenerateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_API_KEY}"
    }
    
    body = {
        "contents": [{
            "parts": [{
                "text": "请用中文写一个简单的Python函数来计算斐波那契数列"
            }]
        }],
        "generationConfig": {
            "maxOutputTokens": 200
        }
    }
    
    async def process_sse_stream(response: httpx.Response) -> AsyncGenerator[str, None]:
        """处理SSE流式响应"""
        buffer = ""
        async for chunk in response.aiter_bytes():
            chunk_str = chunk.decode('utf-8')
            buffer += chunk_str
            
            # 按行分割
            lines = buffer.split('\n')
            buffer = lines[-1] if lines else ""  # 保留未完成的最后一行
            
            for line in lines[:-1]:  # 处理完整的行
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        return
                    
                    try:
                        data_json = json.loads(data)
                        yield data
                    except json.JSONDecodeError:
                        print(f"JSON解析失败: {data}", file=sys.stderr)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            async with client.stream("POST", url, json=body, headers=headers) as response:
                print(f"状态码: {response.status_code}")
                print(f"Content-Type: {response.headers.get('content-type')}")
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    print(f"错误响应: {error_text.decode()}")
                    return
                
                # 收集所有token用于统计
                total_tokens = 0
                collected_text = []
                prompt_tokens = 0
                candidates_tokens = 0
                
                async for data in process_sse_stream(response):
                    try:
                        data_json = json.loads(data)
                        
                        # 解析usageMetadata
                        if "usageMetadata" in data_json:
                            usage = data_json["usageMetadata"]
                            prompt_tokens = usage.get("promptTokenCount", prompt_tokens)
                            candidates_tokens = usage.get("candidatesTokenCount", candidates_tokens)
                        
                        # 解析生成的文本
                        if "candidates" in data_json and len(data_json["candidates"]) > 0:
                            candidate = data_json["candidates"][0]
                            if "content" in candidate and "parts" in candidate["content"]:
                                for part in candidate["content"]["parts"]:
                                    if "text" in part:
                                        text = part["text"]
                                        collected_text.append(text)
                                        print(f"收到chunk: {text}")
                                        total_tokens += len(text) // 4  # 简单估算token数
                    
                    except json.JSONDecodeError as e:
                        print(f"解析chunk失败: {e}", file=sys.stderr)
                    except Exception as e:
                        print(f"处理chunk异常: {e}", file=sys.stderr)
                
                print(f"\n=== 流式传输统计 ===")
                print(f"Prompt tokens: {prompt_tokens}")
                print(f"Candidates tokens: {candidates_tokens}")
                print(f"估算文本长度: {sum(len(t) for t in collected_text)} 字符")
                print(f"估算token数: {total_tokens}")
                print(f"完整响应: {''.join(collected_text)}")
                
        except Exception as e:
            print(f"流式请求异常: {e}")

async def test_x_api_key_header():
    """测试使用x-goog-api-key头部"""
    print("\n=== 测试 x-goog-api-key 头部 ===")
    
    url = f"{BASE_URL}/{MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": TEST_API_KEY
    }
    
    body = {
        "contents": [{
            "parts": [{
                "text": "你好，测试x-goog-api-key头部"
            }]
        }],
        "generationConfig": {
            "maxOutputTokens": 50
        }
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=body, headers=headers)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"x-goog-api-key头部测试成功")
                
                if "candidates" in result and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                print(f"响应: {part['text']}")
            else:
                print(f"错误: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"请求异常: {e}")

async def test_invalid_api_key():
    """测试无效API密钥"""
    print("\n=== 测试无效API密钥 ===")
    
    url = f"{BASE_URL}/{MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer invalid-api-key"
    }
    
    body = {
        "contents": [{
            "parts": [{
                "text": "这个请求应该失败"
            }]
        }]
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=body, headers=headers)
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.text}")
        except Exception as e:
            print(f"请求异常: {e}")

async def main():
    """运行所有测试"""
    print("开始测试Gemini API代理接口")
    print(f"测试地址: {BASE_URL}")
    print(f"测试模型: {MODEL}")
    print(f"测试API密钥: {TEST_API_KEY}")
    print("=" * 50)
    
    # 运行测试
    await test_non_streaming()
    await test_streaming()
    await test_x_api_key_header()
    await test_invalid_api_key()
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(main())