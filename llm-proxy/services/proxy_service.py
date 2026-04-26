"""
代理转发服务
"""

import json
import httpx
from typing import Dict, Any, Optional, AsyncIterator, Tuple
from fastapi import Response
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from models.user import User
from schemas.chat import ChatCompletionRequest, ClaudeMessageRequest
from repositories.upstream_config_repo import UpstreamConfigRepository
from services.billing_service import BillingService
from services.user_service import UserService
from app.config import settings
from log.logger import get_logger

logger = get_logger(__name__)


ALLOWED_HEADERS = {
    "content-type", "accept", "user-agent",
    "x-request-id", "openai-organization"
}


class ProxyService:
    """代理转发服务"""

    def __init__(self):
        self.billing_service = BillingService()
        self.upstream_config_repo = UpstreamConfigRepository()
        self._user_service = UserService()

    def get_upstream_config(self) -> Dict[str, str]:
        """获取上游配置"""
        return {
            "base_url": settings.upstream.base_url,
            "api_key": settings.upstream.api_key,
            "gemini_base_url": settings.upstream.gemini_base_url,
        }

    def _build_error_response(self, code: int, message: str, status_code: int = 400) -> Response:
        """构建错误响应"""
        return Response(
            content=json.dumps({"error": {"code": code, "message": message, "type": "upstream_error"}}),
            status_code=status_code,
            media_type="application/json",
        )

    def _check_balance_and_model(
        self, user_id: int, model: str, db: Session
    ) -> Optional[Response]:
        """检查余额和模型是否启用，通过返回 None，失败返回错误 Response"""
        is_sufficient, _ = self.billing_service.check_balance(user_id, db)
        if not is_sufficient:
            return self._build_error_response(402, "账户余额不足，请充值后再试", 402)
        if self.billing_service.get_model_prices(model, db) is None:
            return self._build_error_response(40001, "模型未启用或不存在")
        return None

    def _do_billing(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> None:
        """统一计费：计算费用 → 记录用量 → 扣除余额"""
        if prompt_tokens <= 0 and completion_tokens <= 0:
            return
        cost = self.billing_service.calculate_cost(
            model, prompt_tokens, completion_tokens, db
        )
        self.billing_service.usage_repo.create(
            user_id=user_id,
            api_key_id=api_key_id,
            model_name=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
            db=db,
        )
        self._user_service.deduct_balance(user_id, cost, db)

    # ---- Gemini token 提取 ----

    @staticmethod
    def _extract_gemini_tokens(data: dict) -> Tuple[int, int]:
        """从 Gemini 响应 data 中提取 (prompt_tokens, candidates_tokens)"""
        usage = data.get("usageMetadata", {})
        return (
            usage.get("promptTokenCount", 0),
            usage.get("candidatesTokenCount", 0),
        )

    @staticmethod
    def _estimate_gemini_tokens_from_body(body_json: dict) -> Tuple[int, int]:
        """从请求体估算 token 数（无法从上游获取 usage 时的 fallback）"""
        total_chars = 0
        for content in body_json.get("contents", []):
            for part in content.get("parts", []):
                if "text" in part:
                    total_chars += len(part["text"])
        estimated_prompt = max(1, total_chars // 4)
        return estimated_prompt, 100

# region
    async def proxy_chat_completions(
        self,
        request_body: bytes,
        user: User,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        转发 OpenAI Chat Completions 请求

        流程：
        1. 解析请求体获取 model 和 stream
        2. 检查余额
        3. 检查模型是否启用
        4. 根据 stream 参数决定上游请求方式
        5. 计费
        6. 透传响应（普通或流式）
        """
        # 解析请求体
        body_json = json.loads(request_body)
        model = body_json.get("model")
        client_stream = body_json.get("stream")  # None/True/False

        # 1. 检查余额和模型
        err = self._check_balance_and_model(user.id, model, db)
        if err:
            return err

        # 2. 获取上游配置并转发
        config = self.get_upstream_config()
        url = f"{config['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }

        # 4. 根据 stream 参数决定上游请求方式
        if client_stream is True or client_stream is None:
            # 客户端要求流式 或 未指定 → 上游请求流式
            return await self._stream_with_billing(
                method="POST",
                url=url,
                headers=headers,
                body=request_body,
                model=model,
                user_id=user.id,
                api_key_id=api_key_id,
                db=db,
            )
        else:
            # 客户端要求非流式 → 上游请求非流式
            return await self._non_stream_with_billing(
                url=url,
                headers=headers,
                body=request_body,
                model=model,
                user_id=user.id,
                api_key_id=api_key_id,
                db=db,
            )

    async def _stream_with_billing(
        self,
        method: str,
        url: str,
        headers: dict,
        body: bytes,
        model: str,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> StreamingResponse:
        """流式请求转发并计费"""
        prompt_tokens = 0
        completion_tokens = 0
        billing_done = False

        async def generate():
            nonlocal prompt_tokens, completion_tokens, billing_done
            async with httpx.AsyncClient(timeout=120.0) as client:
                headers["Accept"] = "text/event-stream"
                async with client.stream(method, url, headers=headers, content=body) as upstream:
                    async for line in upstream.aiter_lines():
                        stripped = line.strip()
                        if not stripped:
                            continue
                        if stripped.startswith("data: "):
                            data_str = stripped[6:]
                            if data_str == "[DONE]":
                                # 流结束时计费
                                if not billing_done:
                                    self._do_billing(
                                        model, prompt_tokens, completion_tokens,
                                        user_id, api_key_id, db,
                                    )
                                    billing_done = True
                                yield b"data: [DONE]\n\n"
                                continue
                            try:
                                data = json.loads(data_str)
                                if "usage" in data and data["usage"]:
                                    prompt_tokens = data["usage"].get("prompt_tokens", 0)
                                    completion_tokens = data["usage"].get("completion_tokens", 0)
                            except json.JSONDecodeError:
                                pass
                            yield f"data: {data_str}\n\n".encode("utf-8")

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )

    async def _non_stream_with_billing(
        self,
        url: str,
        headers: dict,
        body: bytes,
        model: str,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """非流式请求转发并计费"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            upstream = await client.post(url, headers=headers, content=body)
            response_data = upstream.json()

            # 提取 usage 并计费
            prompt_tokens = 0
            completion_tokens = 0
            if "usage" in response_data:
                prompt_tokens = response_data["usage"].get("prompt_tokens", 0)
                completion_tokens = response_data["usage"].get("completion_tokens", 0)
                self._do_billing(
                    model, prompt_tokens, completion_tokens,
                    user_id, api_key_id, db,
                )

            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type="application/json",
            )
# endregion

# region Claude 相关
    async def proxy_claude_messages(
        self,
        request_body: bytes,
        user: User,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        转发 Claude Messages 请求

        流程：
        1. 解析请求体获取 model 和 stream
        2. 检查余额
        3. 检查模型是否启用
        4. 根据 stream 参数决定上游请求方式
        5. 计费
        6. 透传响应（普通或流式）
        """
        # 解析请求体
        body_json = json.loads(request_body)
        model = body_json.get("model")
        client_stream = body_json.get("stream", False)

        # 1. 检查余额和模型
        err = self._check_balance_and_model(user.id, model, db)
        if err:
            return err

        # 2. 获取上游配置并转发
        config = self.get_upstream_config()
        url = f"{config['base_url']}/messages"
        headers = {
            "x-api-key": config["api_key"],
            "Content-Type": "application/json",
        }

        # 4. 根据 stream 参数决定上游请求方式
        if client_stream is True:
            # 客户端要求流式 → 上游请求流式
            return await self._stream_claude_with_billing(
                url=url,
                headers=headers,
                body=request_body,
                model=model,
                user_id=user.id,
                api_key_id=api_key_id,
                db=db,
            )
        else:
            # 客户端要求非流式 → 上游请求非流式
            return await self._non_stream_claude_with_billing(
                url=url,
                headers=headers,
                body=request_body,
                model=model,
                user_id=user.id,
                api_key_id=api_key_id,
                db=db,
            )

    async def _stream_claude_with_billing(
        self,
        url: str,
        headers: dict,
        body: bytes,
        model: str,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> StreamingResponse:
        """Claude 流式请求转发并计费"""
        prompt_tokens = 0
        completion_tokens = 0
        billing_done = False

        async def generate():
            nonlocal prompt_tokens, completion_tokens, billing_done
            async with httpx.AsyncClient(timeout=120.0) as client:
                headers["Accept"] = "text/event-stream"
                async with client.stream("POST", url, headers=headers, content=body) as upstream:
                    buffer = ""
                    async for chunk in upstream.aiter_text():
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
                                        prompt_tokens = data["usage"].get("input_tokens", 0)
                                        completion_tokens = data["usage"].get("output_tokens", 0)
                                except:
                                    pass

                            yield f"event: {event_line}\ndata: {data_content}\n\n".encode("utf-8")

                        # 流结束时计费
                        if not billing_done:
                            self._do_billing(
                                model, prompt_tokens, completion_tokens,
                                user_id, api_key_id, db,
                            )
                            billing_done = True

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )

    async def _non_stream_claude_with_billing(
        self,
        url: str,
        headers: dict,
        body: bytes,
        model: str,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """Claude 非流式请求转发并计费"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            upstream = await client.post(url, headers=headers, content=body)
            response_data = upstream.json()


            # 提取 usage 并计费
            prompt_tokens = 0
            completion_tokens = 0
            if "usage" in response_data:
                prompt_tokens = response_data["usage"].get("input_tokens", 0)
                completion_tokens = response_data["usage"].get("output_tokens", 0)
                self._do_billing(
                    model, prompt_tokens, completion_tokens,
                    user_id, api_key_id, db,
                )

            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type="application/json",
            )
# endregion

# region Gemini 相关
    async def proxy_gemini(
        self,
        model: str,
        method: str,
        request_body: bytes,
        user: User,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        转发 Gemini 请求

        流程：
        1. 检查余额
        2. 检查模型是否启用
        3. 根据 method 参数决定上游请求方式
        4. 计费
        5. 透传响应（普通或流式）
        """
        # 1. 检查余额和模型
        err = self._check_balance_and_model(user.id, model, db)
        if err:
            return err

        # 2. 获取上游配置并转发
        config = self.get_upstream_config()
        url = f"{config['gemini_base_url']}/{model}:{method}"
        
        # 根据 method 参数决定上游请求方式
        if method == "streamGenerateContent":
            # 添加alt=sse参数以确保上游返回SSE格式
            url += "?alt=sse"
            return await self._stream_gemini_with_billing(
                url=url,
                model=model,
                user_id=user.id,
                api_key_id=api_key_id,
                body=request_body,
                db=db,
            )
        else:
            return await self._non_stream_gemini_with_billing(
                url=url,
                model=model,
                user_id=user.id,
                api_key_id=api_key_id,
                body=request_body,
                db=db,
            )

# endregion

    async def proxy_openai_responses(
        self,
        request_body: bytes,
        user: User,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """
        转发 OpenAI Responses 请求

        流程：
        1. 解析请求体获取 model 和 stream
        2. 检查余额
        3. 检查模型是否启用
        4. 根据 stream 参数决定上游请求方式
        5. 计费
        6. 透传响应（普通或流式）
        """
        # 解析请求体
        body_json = json.loads(request_body)
        model = body_json.get("model")
        stream = body_json.get("stream", False)

        # 1. 检查余额和模型
        err = self._check_balance_and_model(user.id, model, db)
        if err:
            return err

        # 2. 获取上游配置并转发
        config = self.get_upstream_config()
        url = f"{config['base_url']}/responses"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        }

        # 4. 根据 stream 参数决定上游请求方式
        if stream:
            return await self._stream_openai_responses_with_billing(
                url=url,
                headers=headers,
                body=body_json,
                model=model,
                user_id=user.id,
                api_key_id=api_key_id,
                db=db,
            )
        else:
            return await self._non_stream_openai_responses_with_billing(
                url=url,
                headers=headers,
                body=body_json,
                model=model,
                user_id=user.id,
                api_key_id=api_key_id,
                db=db,
            )

    async def _non_stream_openai_responses_with_billing(
        self,
        url: str,
        headers: dict,
        body: dict,
        model: str,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> Response:
        """非流式转发并计费"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=body, headers=headers, timeout=30.0)

            if response.status_code != 200:
                return Response(
                    content=response.text,
                    status_code=response.status_code,
                    media_type="application/json",
                )

            result = response.json()

            # 提取 usage 并计费
            input_tokens = 0
            output_tokens = 0
            if "usage" in result:
                usage = result["usage"]
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                self._do_billing(
                    model, input_tokens, output_tokens,
                    user_id, api_key_id, db,
                )

            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type="application/json",
            )

    async def _stream_openai_responses_with_billing(
        self,
        url: str,
        headers: dict,
        body: dict,
        model: str,
        user_id: int,
        api_key_id: int,
        db: Session,
    ) -> StreamingResponse:
        """流式转发并计费"""
        input_tokens = 0
        output_tokens = 0
        billing_done = False

        async def generate():
            nonlocal input_tokens, output_tokens, billing_done
            async with httpx.AsyncClient(timeout=120.0) as client:
                headers["Accept"] = "text/event-stream"
                async with client.stream(
                    "POST",
                    url,
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
                                # 流结束时计费
                                if not billing_done:
                                    self._do_billing(
                                        model, input_tokens, output_tokens,
                                        user_id, api_key_id, db,
                                    )
                                    billing_done = True
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
                            except json.JSONDecodeError:
                                pass

                            yield f"data: {data_str}\n\n".encode("utf-8")

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )

    async def _stream_gemini_with_billing(
        self,
        url: str,
        model: str,
        user_id: int,
        api_key_id: int,
        body: bytes,
        db: Session,
    ) -> StreamingResponse:
        """Gemini 流式请求转发并计费"""
        # 解析请求体获取配置
        body_json = json.loads(body)
        config = self.get_upstream_config()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
            "Accept": "text/event-stream"
        }

        prompt_tokens = 0
        candidates_tokens = 0
        billing_done = False

        async def generate():
            nonlocal prompt_tokens, candidates_tokens, billing_done
            logger.info(f"开始处理Gemini流式请求，模型: {model}, URL: {url}")
            
            # 保存请求的原始body用于可能的fallback计费
            request_body_json = body_json
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, headers=headers, content=body) as upstream:
                    logger.info(f"上游响应状态码: {upstream.status_code}")
                    
                    if upstream.status_code != 200:
                        error_text = await upstream.aread()
                        logger.error(f"上游请求失败: {error_text.decode()}")
                        error_data = json.dumps({
                            "error": {
                                "message": f"Upstream request failed: {upstream.status_code}",
                                "details": error_text.decode()[:500]
                            }
                        })
                        yield f"data: {error_data}\n\n".encode("utf-8")
                        yield b"data: [DONE]\n\n"
                        return

                    content_type = upstream.headers.get("content-type", "").lower()
                    
                    if "text/event-stream" in content_type:
                        # 上游返回SSE格式，逐行处理
                        logger.info("上游返回SSE流式响应")
                        line_count = 0
                        try:
                            async for line in upstream.aiter_lines():
                                line_count += 1
                                stripped = line.strip()
                                logger.debug(f"原始行 {line_count}: {stripped[:200]}")
                                
                                if not stripped:
                                    continue
                                
                                if stripped.startswith("data: "):
                                    data_str = stripped[6:]
                                    
                                    # 处理流结束信号
                                    if data_str == "[DONE]":
                                        logger.info(f"收到[DONE]，行数={line_count}")
                                        if not billing_done:
                                            self._do_billing(
                                                model, prompt_tokens, candidates_tokens,
                                                user_id, api_key_id, db,
                                            )
                                            billing_done = True
                                            logger.info("计费完成")
                                        else:
                                            logger.warn(f"跳过计费: done={billing_done}, p={prompt_tokens}, c={candidates_tokens}")
                                        yield b"data: [DONE]\n\n"
                                        break
                                    
                                    try:
                                        data = json.loads(data_str)
                                        p, c = self._extract_gemini_tokens(data)
                                        if p or c:
                                            prompt_tokens, candidates_tokens = p, c
                                    except json.JSONDecodeError as e:
                                        logger.warn(f"JSON解析失败: {e}")
                                    except Exception as e:
                                        logger.error(f"处理数据失败: {e}")
                                        # 仍然转发原始数据
                                    except Exception as e:
                                        logger.error(f"处理数据失败: {e}")
                                        # 继续转发，不中断流
                                    
                                    # 转发数据（保持SSE格式）
                                    yield f"data: {data_str}\n\n".encode("utf-8")
                                elif stripped.startswith(":"):  # SSE注释行
                                    logger.debug(f"SSE注释行: {stripped[:100]}")
                                else:
                                    logger.warn(f"未知的SSE行格式: {stripped[:100]}")
                        
                        except Exception as e:
                            logger.error(f"流处理异常: {e}")
                            error_data = json.dumps({
                                "error": {
                                    "message": f"Stream processing error: {str(e)}",
                                    "type": "stream_error"
                                }
                            })
                            yield f"data: {error_data}\n\n".encode("utf-8")
                        finally:
                            # 确保发送结束信号
                            logger.info(f"流结束，共处理 {line_count} 行，发送[DONE]信号")
                            logger.info(f"计费状态 - billing_done: {billing_done}, prompt_tokens: {prompt_tokens}, candidates_tokens: {candidates_tokens}")
                            
                            # 如果没有收到[DONE]信号，尝试计费
                            if not billing_done and line_count > 0:
                                logger.warn("未收到[DONE]，尝试fallback计费")
                                if prompt_tokens > 0 or candidates_tokens > 0:
                                    self._do_billing(
                                        model, prompt_tokens, candidates_tokens,
                                        user_id, api_key_id, db,
                                    )
                                    billing_done = True
                                    logger.info("基于已解析数据的fallback计费完成")
                                else:
                                    # 尝试基于请求内容估算
                                    est_p, est_c = self._estimate_gemini_tokens_from_body(request_body_json)
                                    self._do_billing(
                                        model, est_p, est_c,
                                        user_id, api_key_id, db,
                                    )
                                    billing_done = True
                                    logger.info(f"估算计费完成: prompt≈{est_p}, candidates≈{est_c}")
                            
                            yield b"data: [DONE]\n\n"
                    else:
                        # 上游返回JSON格式，包装成SSE格式
                        try:
                            response_body = await upstream.aread()
                            response_text = response_body.decode('utf-8')
                            yield f"data: {response_text}\n\n".encode("utf-8")
                            
                            # 尝试解析usageMetadata
                            try:
                                data_json = json.loads(response_text)
                                p, c = self._extract_gemini_tokens(data_json)
                                if p or c:
                                    prompt_tokens, candidates_tokens = p, c
                                if not billing_done:
                                    self._do_billing(
                                        model, prompt_tokens, candidates_tokens,
                                        user_id, api_key_id, db,
                                    )
                                    billing_done = True
                                    logger.info("JSON响应计费完成")
                                else:
                                    logger.warn("JSON响应: 已跳过计费(已有usageMetadata)")
                            except Exception as e:
                                logger.error(f"解析JSON响应失败: {e}")
                            
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

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )

    async def _non_stream_gemini_with_billing(
        self,
        url: str,
        model: str,
        user_id: int,
        api_key_id: int,
        body: bytes,
        db: Session,
    ) -> Response:
        """Gemini 非流式请求转发并计费"""
        config = self.get_upstream_config()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            upstream = await client.post(url, headers=headers, content=body)
            response_data = upstream.json()

            # 提取 usageMetadata 并计费
            prompt_tokens = 0
            candidates_tokens = 0
            if "usageMetadata" in response_data:
                prompt_tokens, candidates_tokens = self._extract_gemini_tokens(response_data)
                self._do_billing(
                    model, prompt_tokens, candidates_tokens,
                    user_id, api_key_id, db,
                )

            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type="application/json",
            )
