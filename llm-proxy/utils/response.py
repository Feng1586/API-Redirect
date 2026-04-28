"""
统一响应格式
"""

import json
from typing import Any, Optional

from fastapi import Response


def success_response(code: int, message: str, data: Optional[Any] = None) -> dict:
    """成功响应（内部接口使用，如 auth、apikey、user、recharge 等）"""
    response = {
        "code": 0,
        "message": message,
    }
    if data is not None:
        response["data"] = data
    return response


def error_response(code: int, message: str, data: Optional[Any] = None) -> dict:
    """错误响应（内部接口使用，如 auth、apikey、user、recharge 等）"""
    response = {
        "code": code,
        "message": message,
    }
    if data is not None:
        response["data"] = data
    return response


def openai_error_response(
    code: int,
    message: str,
    error_type: str = "api_error",
    status_code: int = 400,
) -> Response:
    """
    OpenAI 兼容错误响应

    用于 chat、chatnostream、responses、gemini、images、videos、tasks 等
    向上游透传的代理接口，错误格式与上游保持一致。
    """
    return Response(
        content=json.dumps({
            "error": {
                "code": code,
                "message": message,
                "type": error_type,
            }
        }),
        status_code=status_code,
        media_type="application/json",
    )


def claude_error_response(
    message: str,
    error_type: str = "api_error",
    status_code: int = 400,
) -> Response:
    """
    Claude 兼容错误响应

    用于 claude 代理接口，错误格式与 Anthropic 上游保持一致。
    """
    return Response(
        content=json.dumps({
            "type": "error",
            "error": {
                "type": error_type,
                "message": message,
            }
        }),
        status_code=status_code,
        media_type="application/json",
    )
