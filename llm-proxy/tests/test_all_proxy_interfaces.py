"""
综合代理接口测试脚本
测试 OpenAI Chat / Claude / OpenAI Responses / Gemini 的流式和非流式接口，
并输出每次请求消耗的输入/输出 tokens。

用法: python test_all_proxy_interfaces.py
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

# ========== 配置 ==========
BASE_URL = "http://127.0.0.1:8000/api/v1"
API_KEY = "sk-qtaj1dixte6rc5mr3sxod149wpoke315"
AUTH_HEADER = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# ========== 测试结果数据类 ==========
@dataclass
class TestResult:
    name: str
    success: bool
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float = 0
    status_code: int = 0
    error: str = ""
    response_preview: str = ""


results: list[TestResult] = []


def print_header(text: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


def print_result(result: TestResult) -> None:
    status = "✅ PASS" if result.success else "❌ FAIL"
    print(f"\n  [{status}] {result.name}")
    print(f"  耗时: {result.duration_ms:.0f}ms | 状态码: {result.status_code}")
    if result.success:
        print(f"  输入 tokens: {result.input_tokens} | 输出 tokens: {result.output_tokens}")
        if result.response_preview:
            print(f"  响应预览: {result.response_preview[:120]}...")
    else:
        print(f"  错误: {result.error}")


# =====================================================================
#  非流式请求辅助函数
# =====================================================================
async def do_non_stream(
    url: str, body: dict, extra_headers: dict | None = None
) -> tuple[int, dict]:
    """发送非流式请求，返回 (status_code, response_json)"""
    headers = {**AUTH_HEADER}
    if extra_headers:
        headers.update(extra_headers)
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=body, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {"_raw": resp.text}
        return resp.status_code, data


# =====================================================================
#  流式 SSE 解析辅助函数
# =====================================================================
async def consume_sse_stream(
    url: str, body: dict,
    extra_headers: dict | None = None,
    token_parser: callable = None,
) -> tuple[int, int, str, int]:
    """
    消费 SSE 流式响应。
    返回: (input_tokens, output_tokens, 拼接文本, status_code)
    token_parser(data_dict, event_type) -> (input_delta, output_delta)
    """
    headers = {**AUTH_HEADER, "Accept": "text/event-stream"}
    if extra_headers:
        headers.update(extra_headers)

    in_tok = 0
    out_tok = 0
    collected_text: list[str] = []
    status_code = 0

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=body, headers=headers) as resp:
            status_code = resp.status_code
            if status_code != 200:
                error_text = await resp.aread()
                return 0, 0, error_text.decode(), status_code

            async for line in resp.aiter_lines():
                stripped = line.strip()
                if not stripped:
                    continue

                if stripped.startswith("data: "):
                    data_str = stripped[6:]
                    if data_str == "[DONE]":
                        continue
                    try:
                        data = json.loads(data_str)
                        if token_parser:
                            di, do = token_parser(data)
                            in_tok = max(in_tok, di)
                            out_tok = max(out_tok, do)
                        # 尝试收集文本
                        txt = _extract_text(data)
                        if txt:
                            collected_text.append(txt)
                    except json.JSONDecodeError:
                        pass
                    except Exception:
                        pass  # 其他解析/提取异常不中断流

                # Claude 的 SSE event: ... data: ... 格式
                elif stripped.startswith("event: "):
                    pass  # 在下一次 data 行中处理

    return in_tok, out_tok, "".join(collected_text), status_code


def _extract_text(data: dict) -> str:
    """通用文本提取（兼容 delta 为 None 的情况）"""
    # OpenAI Chat: choices[0].delta.content（delta 可能为 None）
    for choice in data.get("choices", []):
        delta = choice.get("delta") or {}
        if delta.get("content"):
            return delta["content"]
    # Claude: delta.text
    delta = data.get("delta") or {}
    if delta.get("text"):
        return delta["text"]
    # Gemini: candidates[0].content.parts[*].text
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if part.get("text"):
                return part["text"]
    # OpenAI Responses: 各类事件
    if "text" in data:
        return str(data["text"])
    return ""


# =====================================================================
#  Token 解析器（每种 API 的 usage 位置不同）
# =====================================================================
def parse_openai_chat_tokens(data: dict) -> tuple[int, int]:
    """OpenAI Chat: usage.prompt_tokens / usage.completion_tokens"""
    u = data.get("usage", {})
    return u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def parse_claude_tokens(data: dict) -> tuple[int, int]:
    """Claude: usage.input_tokens / usage.output_tokens (来自 message_delta)"""
    u = data.get("usage", {})
    return u.get("input_tokens", 0), u.get("output_tokens", 0)


def parse_responses_tokens(data: dict) -> tuple[int, int]:
    """OpenAI Responses: response.usage.input_tokens / output_tokens"""
    if data.get("type") == "response.completed":
        u = data.get("response", {}).get("usage", {})
        return u.get("input_tokens", 0), u.get("output_tokens", 0)
    return 0, 0


def parse_gemini_tokens(data: dict) -> tuple[int, int]:
    """Gemini: usageMetadata.promptTokenCount / candidatesTokenCount"""
    u = data.get("usageMetadata", {})
    return u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)


# =====================================================================
#  单测执行器
# =====================================================================
async def run_test(
    name: str,
    url: str,
    body: dict,
    stream: bool = False,
    extra_headers: dict | None = None,
    token_parser: callable = None,
    non_stream_token_parser: callable = None,
) -> None:
    t0 = time.perf_counter()
    try:
        if stream:
            in_tok, out_tok, text, sc = await consume_sse_stream(
                url, body, extra_headers=extra_headers, token_parser=token_parser
            )
            duration = (time.perf_counter() - t0) * 1000
            results.append(TestResult(
                name=name, success=(sc == 200),
                input_tokens=in_tok, output_tokens=out_tok,
                duration_ms=duration, status_code=sc,
                response_preview=text[:200],
                error="" if sc == 200 else text[:300],
            ))
        else:
            sc, data = await do_non_stream(url, body, extra_headers=extra_headers)
            duration = (time.perf_counter() - t0) * 1000
            in_tok, out_tok = 0, 0
            if non_stream_token_parser and sc == 200:
                in_tok, out_tok = non_stream_token_parser(data)

            preview = ""
            if sc == 200:
                preview = _extract_non_stream_text(data)
            results.append(TestResult(
                name=name, success=(sc == 200),
                input_tokens=in_tok, output_tokens=out_tok,
                duration_ms=duration, status_code=sc,
                response_preview=preview[:200],
                error="" if sc == 200 else str(data)[:300],
            ))
    except Exception as e:
        duration = (time.perf_counter() - t0) * 1000
        results.append(TestResult(
            name=name, success=False,
            duration_ms=duration, error=str(e),
        ))


def _extract_non_stream_text(data: dict) -> str:
    """非流式响应中提取文本"""
    # OpenAI Chat
    for choice in data.get("choices", []):
        msg = choice.get("message") or {}
        if msg.get("content"):
            return msg["content"]
    # Claude
    for c in data.get("content", []):
        if c.get("text"):
            return c["text"]
    # Gemini
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if part.get("text"):
                return part["text"]
    # OpenAI Responses
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("text"):
                    return c["text"]
    return ""


def parse_openai_chat_non_stream(data: dict) -> tuple[int, int]:
    u = data.get("usage", {})
    return u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def parse_claude_non_stream(data: dict) -> tuple[int, int]:
    u = data.get("usage", {})
    return u.get("input_tokens", 0), u.get("output_tokens", 0)


def parse_responses_non_stream(data: dict) -> tuple[int, int]:
    u = data.get("usage", {})
    return u.get("input_tokens", 0), u.get("output_tokens", 0)


def parse_gemini_non_stream(data: dict) -> tuple[int, int]:
    u = data.get("usageMetadata", {})
    return u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)


# =====================================================================
#  测试用例定义
# =====================================================================

# ---- OpenAI Chat 消息体 ----
CHAT_MSG = [{"role": "user", "content": "请用中文简要介绍一下Python编程语言，不超过100字。"}]

# ---- Claude 消息体 ----
CLAUDE_MSG = [{"role": "user", "content": "请用中文简要介绍一下Python编程语言，不超过100字。"}]

# ---- OpenAI Responses 消息体 ----
RESPONSES_INPUT = [{
    "role": "user",
    "content": [{"type": "input_text", "text": "请用中文简要介绍一下Python编程语言，不超过100字。"}]
}]

# ---- Gemini 消息体 ----
GEMINI_BODY = {
    "contents": [{
        "parts": [{"text": "请用中文简要介绍一下Python编程语言，不超过100字。"}]
    }],
    "generationConfig": {"maxOutputTokens": 200}
}


async def main() -> None:
    print_header("综合代理接口测试")
    print(f"  Base URL: {BASE_URL}")
    print(f"  API Key : {API_KEY[:20]}...")
    print(f"  开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # ============================================================
    #  1. OpenAI Chat（默认流式）— gpt-5 × 3
    # ============================================================
    print_header("1. OpenAI Chat（默认流式）- /v1/chat/completions")

    url = f"{BASE_URL}/chat/completions"

    # 1a. 不传 stream
    await run_test(
        "Chat(流式) 不带stream", url,
        {"model": "gpt-5", "messages": CHAT_MSG},
        stream=True, token_parser=parse_openai_chat_tokens,
    )

    # 1b. stream=false
    await run_test(
        "Chat(流式) stream=false", url,
        {"model": "gpt-5", "messages": CHAT_MSG, "stream": False},
        stream=False, non_stream_token_parser=parse_openai_chat_non_stream,
    )

    # 1c. stream=true
    await run_test(
        "Chat(流式) stream=true", url,
        {"model": "gpt-5", "messages": CHAT_MSG, "stream": True},
        stream=True, token_parser=parse_openai_chat_tokens,
    )

    # ============================================================
    #  2. OpenAI Chat（默认非流式）— gpt-5 × 3
    # ============================================================
    print_header("2. OpenAI Chat（默认非流式）- /v1/nostream/chat/completions")

    url_ns = f"{BASE_URL}/nostream/chat/completions"

    # 2a. 不传 stream → 默认非流式
    await run_test(
        "Chat(非流) 不带stream", url_ns,
        {"model": "gpt-5", "messages": CHAT_MSG},
        stream=False, non_stream_token_parser=parse_openai_chat_non_stream,
    )

    # 2b. stream=false
    await run_test(
        "Chat(非流) stream=false", url_ns,
        {"model": "gpt-5", "messages": CHAT_MSG, "stream": False},
        stream=False, non_stream_token_parser=parse_openai_chat_non_stream,
    )

    # 2c. stream=true → 会走流式
    await run_test(
        "Chat(非流) stream=true", url_ns,
        {"model": "gpt-5", "messages": CHAT_MSG, "stream": True},
        stream=True, token_parser=parse_openai_chat_tokens,
    )

    # ============================================================
    #  3. Claude — claude-haiku-4-5-20251001 × 2
    # ============================================================
    print_header("3. Claude - /v1/messages")

    claude_url = f"{BASE_URL}/messages"
    claude_body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 200,
        "messages": CLAUDE_MSG,
    }

    # 3a. 非流式
    await run_test(
        "Claude 非流式", claude_url,
        {**claude_body, "stream": False},
        stream=False, non_stream_token_parser=parse_claude_non_stream,
    )

    # 3b. 流式
    await run_test(
        "Claude 流式", claude_url,
        {**claude_body, "stream": True},
        stream=True, token_parser=parse_claude_tokens,
    )

    # ============================================================
    #  4. OpenAI Responses — gpt-5 × 2
    # ============================================================
    print_header("4. OpenAI Responses - /v1/responses")

    resp_url = f"{BASE_URL}/responses"

    # 4a. 非流式
    await run_test(
        "Responses 非流式", resp_url,
        {"model": "gpt-5", "input": RESPONSES_INPUT, "stream": False},
        stream=False, non_stream_token_parser=parse_responses_non_stream,
    )

    # 4b. 流式
    await run_test(
        "Responses 流式", resp_url,
        {"model": "gpt-5", "input": RESPONSES_INPUT, "stream": True},
        stream=True, token_parser=parse_responses_tokens,
    )

    # ============================================================
    #  5. Gemini — gemini-2.5-pro × 2
    # ============================================================
    print_header("5. Gemini - /v1/beta/models/:model:method")

    gemini_base = f"{BASE_URL}/beta/models/gemini-2.5-pro"

    # 5a. 非流式
    await run_test(
        "Gemini 非流式", f"{gemini_base}:generateContent",
        GEMINI_BODY,
        stream=False, non_stream_token_parser=parse_gemini_non_stream,
    )

    # 5b. 流式
    await run_test(
        "Gemini 流式", f"{gemini_base}:streamGenerateContent",
        GEMINI_BODY,
        stream=True, token_parser=parse_gemini_tokens,
    )

    # ============================================================
    #  汇总报告
    # ============================================================
    print_header("测试汇总报告")

    passed = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    total_in = sum(r.input_tokens for r in results)
    total_out = sum(r.output_tokens for r in results)
    total_time = sum(r.duration_ms for r in results)

    for r in results:
        print_result(r)

    print(f"\n{'='*70}")
    print(f"  总计: {len(results)} 个测试 | 通过: {passed} | 失败: {failed}")
    print(f"  总输入 tokens: {total_in} | 总输出 tokens: {total_out}")
    print(f"  总耗时: {total_time:.0f}ms ({total_time/1000:.1f}s)")
    print(f"{'='*70}\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
