from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import logging
import json
import re

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPSTREAM_BASE_URL = "https://api.apimart.ai/v1beta/models"
OUR_API_KEY = "sk-An7bxzzKGHsqNs9b8U4ZGvXfmiL3utujmbPflSro0UUmU9Xu"
# 根据调试结果，gemini-2.5-flash 是可用的模型
DEFAULT_MODEL = "gemini-2.5-flash"

# @app.get("/")
# async def root():
#     """健康检查端点"""
#     return {"status": "ok", "service": "Gemini API Proxy"}

# @app.get("/debug/models")
# async def debug_models():
#     """调试端点：测试上游API"""
#     import httpx
#     headers = {
#         "Content-Type": "application/json",
#         "Authorization": f"Bearer {OUR_API_KEY}"
#     }
    
#     async with httpx.AsyncClient() as client:
#         try:
#             response = await client.get(
#                 f"{UPSTREAM_BASE_URL}",
#                 headers=headers,
#                 timeout=10.0
#             )
#             return {
#                 "status_code": response.status_code,
#                 "response": response.json() if response.status_code == 200 else response.text
#             }
#         except Exception as e:
#             return {"error": str(e)}

@app.post("/v1beta/models/{model}:{method}")
async def proxy_request(model: str, method: str, request: Request):
    auth_header = request.headers.get("authorization", "")
    x_api_key = request.headers.get("x-goog-api-key", "")
    
    user_api_key = ""
    if auth_header.startswith("Bearer "):
        user_api_key = auth_header[7:]
    elif x_api_key:
        user_api_key = x_api_key
    
    logger.info(f"User API Key: {user_api_key}")
    logger.info(f"Model: {model}")
    
    body = await request.json()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OUR_API_KEY}"
    }
    
    # 构建上游URL，对于流式请求添加alt=sse参数
    upstream_url = f"{UPSTREAM_BASE_URL}/{model}:{method}"
    
    if method == "streamGenerateContent":
        # 添加alt=sse参数以确保上游返回SSE格式
        upstream_url += "?alt=sse"
        logger.info(f"流式请求URL: {upstream_url}")
        
        return StreamingResponse(
            stream_upstream(upstream_url, headers, body),
            media_type="text/event-stream"  # 改为SSE标准媒体类型
        )
    else:
        logger.info(f"非流式请求URL: {upstream_url}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                upstream_url,
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
            if "usageMetadata" in result:
                usage = result["usageMetadata"]
                prompt_tokens = usage.get("promptTokenCount", 0)
                candidates_tokens = usage.get("candidatesTokenCount", 0)
                logger.info(f"Prompt tokens: {prompt_tokens}")
                logger.info(f"Candidates tokens: {candidates_tokens}")
            
            return result

async def stream_upstream(url: str, headers: dict, body: dict):
    prompt_tokens = 0
    candidates_tokens = 0
    
    async with httpx.AsyncClient() as client:
        # 设置Accept头部为text/event-stream以确保上游返回SSE格式
        headers["Accept"] = "text/event-stream"
        
        async with client.stream(
            "POST",
            url,
            json=body,
            headers=headers,
            timeout=120.0
        ) as response:
            logger.info(f"上游响应状态码: {response.status_code}")
            logger.info(f"上游响应头: {dict(response.headers)}")
            
            if response.status_code != 200:
                # 读取错误信息
                error_text = await response.aread()
                logger.error(f"上游请求失败: {error_text.decode()}")
                # 返回错误信息给客户端
                error_data = json.dumps({
                    "error": {
                        "message": f"Upstream request failed: {response.status_code}",
                        "details": error_text.decode()[:500]
                    }
                })
                yield f"data: {error_data}\n\n".encode("utf-8")
                yield b"data: [DONE]\n\n"
                return
            
            # 检查上游响应类型
            content_type = response.headers.get("content-type", "").lower()
            
            if "text/event-stream" in content_type:
                # 上游返回SSE格式，逐行处理
                logger.info("上游返回SSE流式响应")
                try:
                    async for line in response.aiter_lines():
                        stripped = line.strip()
                        if not stripped:
                            continue
                        
                        logger.debug(f"收到SSE行: {stripped[:200]}")
                        
                        # 处理SSE数据行
                        if stripped.startswith("data: "):
                            data_str = stripped[6:]
                            
                            # 处理流结束信号
                            if data_str == "[DONE]":
                                logger.info("收到结束信号 [DONE]")
                                yield b"data: [DONE]\n\n"
                                break
                            
                            try:
                                # 解析JSON数据
                                data_json = json.loads(data_str)
                                
                                # 解析usageMetadata
                                if "usageMetadata" in data_json:
                                    usage = data_json["usageMetadata"]
                                    prompt_tokens = usage.get("promptTokenCount", prompt_tokens)
                                    candidates_tokens = usage.get("candidatesTokenCount", candidates_tokens)
                                    logger.debug(f"更新tokens统计: prompt={prompt_tokens}, candidates={candidates_tokens}")
                                
                                # 转发数据（保持SSE格式）
                                yield f"data: {data_str}\n\n".encode("utf-8")
                                
                            except json.JSONDecodeError as e:
                                logger.warning(f"JSON解析失败: {e}, 数据: {data_str[:100]}")
                                # 仍然转发原始数据
                                yield f"data: {data_str}\n\n".encode("utf-8")
                            except Exception as e:
                                logger.error(f"处理数据失败: {e}")
                                # 继续转发，不中断流
                        
                        elif stripped.startswith(":"):  # SSE注释行
                            continue
                        else:
                            logger.warning(f"未知的SSE行格式: {stripped[:100]}")
                
                except httpx.ReadTimeout:
                    logger.error("读取上游响应超时")
                    # 发送超时错误
                    timeout_data = json.dumps({
                        "error": {
                            "message": "Upstream stream timeout",
                            "type": "timeout_error"
                        }
                    })
                    yield f"data: {timeout_data}\n\n".encode("utf-8")
                except Exception as e:
                    logger.error(f"流处理异常: {e}")
                    # 发送异常错误
                    error_data = json.dumps({
                        "error": {
                            "message": f"Stream processing error: {str(e)}",
                            "type": "stream_error"
                        }
                    })
                    yield f"data: {error_data}\n\n".encode("utf-8")
                finally:
                    # 确保发送结束信号
                    logger.info("流结束，发送[DONE]信号")
                    yield b"data: [DONE]\n\n"
                    
            else:
                # 上游返回JSON格式，需要将其包装成SSE格式
                logger.info(f"上游返回JSON响应，content-type: {content_type}")
                
                try:
                    # 读取完整的响应体
                    response_body = await response.aread()
                    response_text = response_body.decode('utf-8')
                    
                    logger.debug(f"完整响应体: {response_text[:500]}...")
                    
                    try:
                        # 解析JSON响应
                        data_json = json.loads(response_text)
                        
                        # 解析usageMetadata
                        if "usageMetadata" in data_json:
                            usage = data_json["usageMetadata"]
                            prompt_tokens = usage.get("promptTokenCount", 0)
                            candidates_tokens = usage.get("candidatesTokenCount", 0)
                            logger.info(f"从JSON响应中解析tokens: prompt={prompt_tokens}, candidates={candidates_tokens}")
                        
                        # 将完整JSON包装成SSE格式返回
                        # 这是为了保持与SSE客户端的兼容性
                        yield f"data: {response_text}\n\n".encode("utf-8")
                        
                        # 发送结束信号
                        yield b"data: [DONE]\n\n"
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"无法解析上游JSON响应: {e}")
                        # 返回错误信息
                        error_data = json.dumps({
                            "error": {
                                "message": f"Failed to parse upstream JSON response: {str(e)}",
                                "type": "json_parse_error"
                            }
                        })
                        yield f"data: {error_data}\n\n".encode("utf-8")
                        yield b"data: [DONE]\n\n"
                        
                except Exception as e:
                    logger.error(f"读取上游响应失败: {e}")
                    error_data = json.dumps({
                        "error": {
                            "message": f"Failed to read upstream response: {str(e)}",
                            "type": "read_error"
                        }
                    })
                    yield f"data: {error_data}\n\n".encode("utf-8")
                    yield b"data: [DONE]\n\n"
    
    # 流结束后输出统计
    logger.info(f"Stream completed - Prompt tokens: {prompt_tokens}, Candidates tokens: {candidates_tokens}")