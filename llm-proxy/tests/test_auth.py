"""
认证接口测试
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestAuth:
    """认证测试"""

    def test_register_success(self):
        """测试成功注册"""
        # TODO: 实现注册测试
        pass

    def test_register_email_exists(self):
        """测试邮箱已注册"""
        # TODO: 实现邮箱已注册测试
        pass

    def test_register_invalid_code(self):
        """测试验证码错误"""
        # TODO: 实现验证码错误测试
        pass

    def test_login_success(self):
        """测试成功登录"""
        # TODO: 实现登录测试
        pass

    def test_login_wrong_password(self):
        """测试密码错误"""
        # TODO: 实现密码错误测试
        pass

    def test_login_locked(self):
        """测试登录锁定"""
        # TODO: 实现登录锁定测试
        pass

    def test_logout(self):
        """测试退出登录"""
        # TODO: 实现退出登录测试
        pass
