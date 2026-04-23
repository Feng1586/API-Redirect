"""
PayPal 支付流程独立测试脚本
用于测试 PayPal OAuth 认证 + 创建订单

使用方式:
  python -m tests.test_paypal_flow

测试流程:
  1. 测试 OAuth 2.0 获取 Access Token
  2. 测试创建订单（intent=CAPTURE）
  3. （可选）手动测试捕获订单

注意:
  运行前请确保 config.yaml 中已配置好 PayPal 沙箱凭据
  - paypal.client_id
  - paypal.client_secret
"""

import asyncio
import json
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.paypal_service import PayPalService


async def test_oauth():
    """测试 1: OAuth 2.0 获取 Access Token"""
    print("\n" + "=" * 60)
    print("📌 测试 1: OAuth 2.0 获取 Access Token")
    print("=" * 60)

    service = PayPalService()
    success, message, token = await service.get_access_token()

    if success:
        print(f"✅ 成功: {message}")
        print(f"   Token: {token[:50]}...")
        return True, token
    else:
        print(f"❌ 失败: {message}")
        return False, None


async def test_create_order(amount: str = "10.00"):
    """测试 2: 创建 PayPal 订单"""
    print("\n" + "=" * 60)
    print(f"📌 测试 2: 创建订单 (金额: {amount} USD)")
    print("=" * 60)

    service = PayPalService()
    success, message, data = await service.create_order(
        amount=amount,
        currency="USD",
        custom_id=f"TEST-ORDER-{asyncio.get_event_loop().time():.0f}",
        return_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        description="测试订单 - AI API 充值",
    )

    if success:
        print(f"✅ 成功: {message}")
        print(f"   PayPal Order ID: {data['paypal_order_id']}")
        print(f"   订单状态: {data['status']}")
        print(f"   Approve URL: {data['approve_url']}")
        print()
        print("👉 下一步: 在浏览器中打开 Approve URL")
        print("   使用沙箱买家账号登录并批准支付")
        print("   然后将 PayPal Order ID 用于测试 3")
        return True, data
    else:
        print(f"❌ 失败: {message}")
        return False, None


async def test_capture_order(paypal_order_id: str):
    """测试 3: 捕获订单（扣款）"""
    print("\n" + "=" * 60)
    print(f"📌 测试 3: 捕获订单 (PayPal Order ID: {paypal_order_id})")
    print("=" * 60)

    service = PayPalService()
    success, message, data = await service.capture_order(paypal_order_id)

    if success:
        print(f"✅ 成功: {message}")
        print(f"   订单状态: {data['status']}")
        captures = data.get("captures", [])
        for cap in captures:
            print(f"   Capture ID: {cap['capture_id']}")
            print(f"   捕获状态: {cap['status']}")
            print(f"   金额: {cap['amount']} {cap['currency']}")
            print(f"   手续费: {cap['seller_receivable_breakdown'].get('paypal_fee', {}).get('value', 'N/A')}")
            print(f"   净收入: {cap['seller_receivable_breakdown'].get('net_amount', {}).get('value', 'N/A')}")
        return True, data
    else:
        print(f"❌ 失败: {message}")
        return False, None


async def test_get_order(paypal_order_id: str):
    """测试 4: 查询订单状态"""
    print("\n" + "=" * 60)
    print(f"📌 测试 4: 查询订单状态 (PayPal Order ID: {paypal_order_id})")
    print("=" * 60)

    service = PayPalService()
    success, message, data = await service.get_order(paypal_order_id)

    if success:
        print(f"✅ 成功: {message}")
        print(f"   订单状态: {data.get('status', '')}")
        print(f"   订单 ID: {data.get('id', '')}")
        return True, data
    else:
        print(f"❌ 失败: {message}")
        return False, None


async def main():
    """主测试流程"""
    print("🎯 PayPal 支付流程测试")
    print("环境: Sandbox (沙箱)")
    print(f"Base URL: {PayPalService().base_url}")
    print()

    # 测试 1: OAuth
    oauth_ok, token = await test_oauth()
    if not oauth_ok:
        print("\n❌ OAuth 认证失败，终止测试")
        print("请检查 config.yaml 中的 paypal.client_id 和 paypal.client_secret")
        return

    # 测试 2: 创建订单
    order_ok, order_data = await test_create_order("10.00")
    if not order_ok:
        print("\n❌ 创建订单失败，终止测试")
        return

    paypal_order_id = order_data["paypal_order_id"]

    print()
    print("-" * 60)
    print("📋 测试总结")
    print("-" * 60)
    print(f"PayPal Order ID: {paypal_order_id}")
    print(f"Approve URL: {order_data['approve_url']}")
    print()
    print("🔔 后续步骤:")
    print("1. 打开 Approve URL，用沙箱买家账号登录")
    print("2. 批准支付（不需要真实付款，沙箱环境）")
    print("3. 获得批准后，运行带参数的捕获测试:")
    print(f"   python -c \"import asyncio; from tests.test_paypal_flow import test_capture_order; asyncio.run(test_capture_order('{paypal_order_id}'))\"")
    print()
    print("💡 使用 Postman 测试 FastAPI 接口:")
    print("   Step 1: POST /api/v1/recharge/paypal/create")
    print('     Body: {"amount": 10.00, "currency": "USD", "return_url": "", "cancel_url": ""}')
    print("   Step 2: POST /api/v1/recharge/paypal/capture")
    print('     Body: {"order_no": "<从Step1返回的order_no>"}')
    print()


if __name__ == "__main__":
    asyncio.run(main())
