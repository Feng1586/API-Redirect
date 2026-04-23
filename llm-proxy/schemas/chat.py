"""
对话请求/响应模型
"""

from typing import Optional, Any, List, Union
from pydantic import BaseModel, Field


class Message(BaseModel):
    """消息"""
    role: str
    content: Union[str, List[dict]]


class ChatCompletionRequest(BaseModel):
    """OpenAI Chat Completions 请求"""
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = True
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    user: Optional[str] = None


class ClaudeMessageRequest(BaseModel):
    """Claude Messages 请求"""
    model: str
    messages: List[Message]
    max_tokens: int = 1024
    temperature: Optional[float] = 1.0
    stream: Optional[bool] = False


class ResponseRequest(BaseModel):
    """OpenAI Responses 请求"""
    model: str
    input: Union[str, List[dict]]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    max_tokens: Optional[int] = None
