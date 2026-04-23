"""
统一响应格式
"""

from typing import Any, Optional


def success_response(code: int, message: str, data: Optional[Any] = None) -> dict:
    """成功响应"""
    response = {
        "code": 0,
        "message": message,
    }
    if data is not None:
        response["data"] = data
    return response


def error_response(code: int, message: str, data: Optional[Any] = None) -> dict:
    """错误响应"""
    response = {
        "code": code,
        "message": message,
    }
    if data is not None:
        response["data"] = data
    return response
