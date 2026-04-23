"""
API-Key接口测试
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestApiKey:
    """API-Key测试"""

    def test_create_api_key(self):
        """测试创建API-Key"""
        # TODO: 实现创建API-Key测试
        pass

    def test_list_api_keys(self):
        """测试获取API-Key列表"""
        # TODO: 实现获取列表测试
        pass

    def test_delete_api_key(self):
        """测试删除API-Key"""
        # TODO: 实现删除API-Key测试
        pass

    def test_update_api_key_name(self):
        """测试修改API-Key备注"""
        # TODO: 实现修改备注测试
        pass

    def test_api_key_limit(self):
        """测试API-Key数量上限"""
        # TODO: 实现数量上限测试
        pass
