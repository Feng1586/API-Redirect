"""
代理接口测试
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestProxy:
    """代理转发测试"""

    def test_chat_completions_success(self):
        """测试Chat Completions成功"""
        # TODO: 实现Chat Completions测试
        pass

    def test_chat_completions_insufficient_balance(self):
        """测试余额不足"""
        # TODO: 实现余额不足测试
        pass

    def test_claude_messages(self):
        """测试Claude Messages"""
        # TODO: 实现Claude Messages测试
        pass

    def test_gemini(self):
        """测试Gemini"""
        # TODO: 实现Gemini测试
        pass

    def test_openai_responses(self):
        """测试OpenAI Responses"""
        # TODO: 实现OpenAI Responses测试
        pass
