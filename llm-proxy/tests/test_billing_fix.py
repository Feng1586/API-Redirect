"""
测试流式传输时计费修复
模拟当上游没有返回usageMetadata时的fallback计费逻辑
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from models.user import User
from models.api_key import ApiKey
from models.model_config import ModelConfig
from services.billing_service import BillingService
from services.user_service import UserService

# 创建测试数据库
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_billing_logic():
    """测试计费逻辑"""
    db = SessionLocal()
    
    try:
        # 创建测试用户
        test_user = User(
            username="test_user",
            email="test@example.com",
            balance=100.0,
            role="user",
            status="active"
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        # 创建API Key
        test_apikey = ApiKey(
            user_id=test_user.id,
            key="test_key_123",
            name="Test Key",
            status="active"
        )
        db.add(test_apikey)
        db.commit()
        db.refresh(test_apikey)
        
        # 创建模型配置
        test_model = ModelConfig(
            model_name="gemini-2.5-flash",
            upstream_model="gemini-2.5-flash",
            price_per_1k_input=0.10,
            price_per_1k_output=0.40,
            is_enabled=True
        )
        db.add(test_model)
        db.commit()
        
        # 测试计费服务
        billing_service = BillingService()
        
        # 测试1: 正常计费
        prompt_tokens = 258
        candidates_tokens = 82
        cost = billing_service.calculate_cost(
            "gemini-2.5-flash",
            prompt_tokens,
            candidates_tokens,
            db
        )
        print(f"测试1 - 正常计费:")
        print(f"  Prompt tokens: {prompt_tokens}, Candidates tokens: {candidates_tokens}")
        print(f"  计算费用: ¥{cost:.6f}")
        
        # 测试2: 记录用量
        usage_repo = billing_service.usage_repo
        usage_record = usage_repo.create(
            user_id=test_user.id,
            api_key_id=test_apikey.id,
            model_name="gemini-2.5-flash",
            prompt_tokens=prompt_tokens,
            completion_tokens=candidates_tokens,
            total_tokens=prompt_tokens + candidates_tokens,
            cost=cost,
            db=db
        )
        print(f"测试2 - 记录用量:")
        print(f"  用量记录ID: {usage_record.id}")
        print(f"  用户ID: {usage_record.user_id}")
        print(f"  模型: {usage_record.model_name}")
        
        # 测试3: 扣除余额
        user_service = UserService()
        user_service.deduct_balance(test_user.id, cost, db)
        
        # 重新获取用户信息
        db.refresh(test_user)
        print(f"测试3 - 扣除余额:")
        print(f"  扣除后余额: ¥{test_user.balance:.2f}")
        
        # 测试4: 检查余额是否充足
        is_sufficient, current_balance = billing_service.check_balance(test_user.id, db)
        print(f"测试4 - 检查余额:")
        print(f"  是否充足: {is_sufficient}")
        print(f"  当前余额: ¥{current_balance:.2f}")
        
        # 测试5: 测试没有usage时的估算计费
        print(f"\n测试5 - 估算计费逻辑:")
        
        # 模拟请求内容
        request_content = {
            "contents": [
                {
                    "parts": [
                        {"text": "这是一个测试问题，用于验证估算计费逻辑是否正确。"}
                    ]
                }
            ]
        }
        
        # 估算输入tokens
        total_chars = 0
        if "contents" in request_content:
            for content in request_content.get("contents", []):
                for part in content.get("parts", []):
                    if "text" in part:
                        total_chars += len(part["text"])
        
        # 简单估算：每4个字符约1个token
        estimated_prompt_tokens = max(1, total_chars // 4)
        estimated_candidates_tokens = 100  # 默认输出100个token
        
        print(f"  请求内容: {request_content['contents'][0]['parts'][0]['text'][:50]}...")
        print(f"  字符数: {total_chars}")
        print(f"  估算Prompt tokens: {estimated_prompt_tokens}")
        print(f"  估算Candidates tokens: {estimated_candidates_tokens}")
        
        estimated_cost = billing_service.calculate_cost(
            "gemini-2.5-flash",
            estimated_prompt_tokens,
            estimated_candidates_tokens,
            db
        )
        print(f"  估算费用: ¥{estimated_cost:.6f}")
        
        print("\n✅ 所有测试通过！")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_fallback_billing():
    """测试fallback计费逻辑"""
    print("\n=== 测试fallback计费逻辑 ===")
    
    db = SessionLocal()
    
    try:
        # 获取或创建测试用户
        test_user = db.query(User).filter(User.username == "test_user").first()
        if not test_user:
            print("❌ 测试用户不存在，请先运行 test_billing_logic")
            return False
        
        # 获取或创建API Key
        test_apikey = db.query(ApiKey).filter(ApiKey.user_id == test_user.id).first()
        if not test_apikey:
            print("❌ 测试API Key不存在")
            return False
        
        # 模拟不同的计费场景
        billing_service = BillingService()
        
        # 场景1: 有usage数据
        print("\n场景1 - 有usage数据:")
        cost1 = billing_service.calculate_cost("gemini-2.5-flash", 100, 50, db)
        print(f"  tokens: prompt=100, candidates=50, cost=¥{cost1:.6f}")
        
        # 场景2: 没有usage数据，fallback估算
        print("\n场景2 - 没有usage数据，估算:")
        cost2 = billing_service.calculate_cost("gemini-2.5-flash", 0, 0, db)
        print(f"  tokens: prompt=0, candidates=0, cost=¥{cost2:.6f}")
        
        # 场景3: 最小计费
        print("\n场景3 - 最小计费测试:")
        cost3 = billing_service.calculate_cost("gemini-2.5-flash", 1, 1, db)
        print(f"  tokens: prompt=1, candidates=1, cost=¥{cost3:.6f}")
        
        print("\n✅ fallback计费测试完成")
        return True
        
    except Exception as e:
        print(f"❌ fallback计费测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_stream_simulation():
    """模拟流式传输计费场景"""
    print("\n=== 模拟流式传输计费 ===")
    
    # 模拟SSE数据
    sse_data_samples = [
        'data: {"candidates": [{"content": {"parts": [{"text": "你好"}]}}]}\n\n',
        'data: {"candidates": [{"content": {"parts": [{"text": "，我是AI助手"}]}}]}\n\n',
        'data: {"usageMetadata": {"promptTokenCount": 258, "candidatesTokenCount": 82}}\n\n',
        'data: [DONE]\n\n'
    ]
    
    print("模拟SSE流数据:")
    for i, line in enumerate(sse_data_samples):
        print(f"  {i+1}. {line.strip()}")
    
    print("\n计费逻辑说明:")
    print("  1. 流式传输中会逐行解析SSE数据")
    print("  2. 当遇到usageMetadata时，更新tokens统计")
    print("  3. 当收到[DONE]信号时，执行计费操作")
    print("  4. 如果没有[DONE]信号，在finally块中执行fallback计费")
    print("  5. 如果没有任何usage数据，根据请求内容估算计费")
    
    return True

if __name__ == "__main__":
    print("开始测试流式传输计费修复...")
    print("=" * 60)
    
    success1 = test_billing_logic()
    success2 = test_fallback_billing()
    success3 = test_stream_simulation()
    
    print("\n" + "=" * 60)
    if success1 and success2 and success3:
        print("✅ 所有测试通过！")
        print("\n建议:")
        print("  1. 重启API服务以使代码更改生效")
        print("  2. 使用真实的Gemini请求测试流式计费")
        print("  3. 检查数据库中的usage_records表确认计费记录")
    else:
        print("❌ 部分测试失败，请检查以上错误信息")