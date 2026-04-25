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
from models.task_record import TaskRecord
from models.video_model_config import VideoModelConfig, VideoResolutionPrice
from models.image_model_config import ImageModelConfig, ImageResolutionPrice


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
            # 图片/视频生成模型（price_per_1k_input 即为单次调用固定费用）
            {"model_name": "gemini-3.1-flash-image-preview", "price_per_1k_input": 0.05, "price_per_1k_output": 0.05},
        ]

        for config in configs:
            model_config = ModelConfig(**config)
            session.add(model_config)

        session.commit()
        print("模型配置初始化完成！")


def init_video_model_configs():
    """初始化视频模型配置"""
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        # 检查是否已有配置
        existing = session.query(VideoModelConfig).first()
        if existing:
            print("视频模型配置已存在，跳过初始化")
            return

        # 视频模型配置: 模型名, 默认时长(秒), [ (分辨率, 每秒单价, 是否默认), ... ]
        video_configs = [
            {
                "model_name": "kling-1.5",
                "default_duration": 5,
                "resolutions": [
                    ("720p", 0.02, 1),
                    ("1080p", 0.04, 0),
                ],
            },
            {
                "model_name": "kling-1.5-pro",
                "default_duration": 10,
                "resolutions": [
                    ("720p", 0.04, 1),
                    ("1080p", 0.08, 0),
                ],
            },
        ]

        for config in video_configs:
            resolutions = config.pop("resolutions")
            model = VideoModelConfig(**config)
            session.add(model)
            session.flush()  # 获取 model.id

            for resolution, price, is_default in resolutions:
                resolution_price = VideoResolutionPrice(
                    model_id=model.id,
                    resolution=resolution,
                    price_per_second=price,
                    is_default=is_default,
                )
                session.add(resolution_price)

        session.commit()
        print("视频模型配置初始化完成！")


def init_image_model_configs():
    """初始化图片模型配置"""
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        # 检查是否已有配置
        existing = session.query(ImageModelConfig).first()
        if existing:
            print("图片模型配置已存在，跳过初始化")
            return

        # 图片模型配置: 模型名, [ (分辨率, 每张单价, 是否默认), ... ]
        image_configs = [
            {
                "model_name": "dall-e-3",
                "resolutions": [
                    ("1024x1024", 0.04, 1),
                    ("1024x1792", 0.08, 0),
                    ("1792x1024", 0.08, 0),
                ],
            },
            {
                "model_name": "dall-e-2",
                "resolutions": [
                    ("1024x1024", 0.02, 1),
                    ("512x512", 0.018, 0),
                    ("256x256", 0.016, 0),
                ],
            },
            {
                "model_name": "gemini-3.1-flash-image-preview",
                "resolutions": [
                    ("default", 0.05, 1),
                ],
            },
        ]

        for config in image_configs:
            resolutions = config.pop("resolutions")
            model = ImageModelConfig(**config)
            session.add(model)
            session.flush()  # 获取 model.id

            for resolution, price, is_default in resolutions:
                resolution_price = ImageResolutionPrice(
                    model_id=model.id,
                    resolution=resolution,
                    price_per_image=price,
                    is_default=is_default,
                )
                session.add(resolution_price)

        session.commit()
        print("图片模型配置初始化完成！")


if __name__ == "__main__":
    init_db()
    init_model_configs()
    init_video_model_configs()
    init_image_model_configs()
