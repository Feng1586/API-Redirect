"""
用量响应模型
"""

from typing import List
from pydantic import BaseModel


class DailyUsage(BaseModel):
    """每日用量"""
    date: str
    tokens: int
    cost: float
    requests: int


class UsageResponse(BaseModel):
    """用量响应"""
    daily_usage: List[DailyUsage]
    total_tokens: int
    total_cost: float
