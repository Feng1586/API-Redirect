"""
数据库初始化脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 切换工作目录到项目根目录，确保能找到 config.yaml
import os
os.chdir(project_root)

from app.database import engine, Base
from models.user import User
from models.api_key import ApiKey
from models.order import Order
from models.model_config import ModelConfig
from models.usage import UsageRecord


def init_db():
    """初始化数据库表"""
    print("正在创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成！")


def init_model_configs():
    """初始化模型配置"""
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        # 检查是否已有配置
        existing = session.query(ModelConfig).first()
        if existing:
            print("模型配置已存在，跳过初始化")
            return

        # 默认模型配置 (价格单位: 元/1K tokens)
        # input: 输入tokens价格, output: 输出tokens价格
        configs = [
            {"model_name": "gpt-4", "price_per_1k_input": 0.03, "price_per_1k_output": 0.06},
            {"model_name": "gpt-4-turbo", "price_per_1k_input": 0.01, "price_per_1k_output": 0.03},
            {"model_name": "gpt-3.5-turbo", "price_per_1k_input": 0.0005, "price_per_1k_output": 0.0015},
            {"model_name": "claude-3-opus-20240229", "price_per_1k_input": 0.015, "price_per_1k_output": 0.075},
            {"model_name": "claude-3-sonnet-20240229", "price_per_1k_input": 0.003, "price_per_1k_output": 0.015},
            {"model_name": "gemini-pro", "price_per_1k_input": 0.001, "price_per_1k_output": 0.002},
        ]

        for config in configs:
            model_config = ModelConfig(**config)
            session.add(model_config)

        session.commit()
        print("模型配置初始化完成！")


if __name__ == "__main__":
    init_db()
    init_model_configs()
